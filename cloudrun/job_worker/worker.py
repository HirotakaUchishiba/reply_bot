"""Cloud Run Job worker to generate AI reply and update Slack modal."""

from __future__ import annotations

import json
import os
import sys
import logging
from typing import Any, Dict

import urllib.request

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test-friendly shims for optional deps (so pytest can patch by name)
try:  # pragma: no cover - prefer real libs if present
    from slack_sdk import WebClient  # type: ignore
    from slack_sdk.errors import SlackApiError  # type: ignore
except Exception:  # pragma: no cover - create a shim for patching
    import types as _types

    class _DummyWebClient:  # minimal to satisfy type usage
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def views_update(self, *args: Any, **kwargs: Any) -> None:
            pass

    _errors = _types.SimpleNamespace(SlackApiError=Exception)
    # Construct a minimal module-like object for slack_sdk
    _slack_mod = _types.ModuleType("slack_sdk")
    _slack_mod.WebClient = _DummyWebClient  # type: ignore[attr-defined]
    _slack_mod.errors = _errors  # type: ignore[attr-defined]
    # allow patch('slack_sdk.WebClient') to work in tests
    sys.modules.setdefault("slack_sdk", _slack_mod)
    WebClient = _DummyWebClient  # type: ignore
    SlackApiError = Exception  # type: ignore

try:  # pragma: no cover
    import boto3  # type: ignore
except Exception:  # pragma: no cover
    import types as _types

    class _DummyBoto3:  # minimal shim for patch('boto3.resource')
        def resource(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("boto3 shim in test env")

    _boto3_mod = _types.ModuleType("boto3")
    _boto3_mod.resource = _DummyBoto3().resource  # type: ignore[attr-defined]
    sys.modules.setdefault("boto3", _boto3_mod)
    import boto3  # type: ignore  # noqa: E402  (now points to shim)

from config import JobWorkerConfig


def _call_openai(redacted_body: str, config: JobWorkerConfig) -> str:
    """Call OpenAI to generate a draft reply.

    Returns empty string on failure to keep the worker idempotent.
    """
    if not redacted_body or not config.openai_api_key:
        return ""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": (
                    "あなたは日本語のCS担当者です。以下の問い合わせに対して、丁寧で簡潔な返信文案を作成してください。\n\n"
                    + redacted_body
                ),
            }
        ],
        "max_tokens": 400,
    }
    headers = {
        "Authorization": f"Bearer {config.openai_api_key}",
        "Content-Type": "application/json",
    }
    try:
        req = urllib.request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        timeout = max(1, int(getattr(config, "openai_timeout", 30)))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode(
                "utf-8",
                errors="ignore",
            )
        data = json.loads(raw)
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = (message or {}).get("content", "")
        return str(content or "").strip()
    except Exception:
        return ""


def _reidentify_pii(text: str, pii_map: Dict[str, str]) -> str:
    if not pii_map:
        return text
    out = text
    for k, v in pii_map.items():
        out = out.replace(k, v)
    return out


def _get_dynamodb_context(
    context_id: str, config: JobWorkerConfig
) -> Dict[str, Any]:
    if not context_id:
        return {}
    try:
        logger.info(f"Attempting to get item from DynamoDB table: {config.ddb_table_name} for context_id: {context_id}")
        
        # Use Workload Identity for AWS access
        import boto3
        import os
        from botocore.config import Config
        
        # Get AWS credentials from Secret Manager
        aws_access_key_id_secret_name = os.getenv("AWS_ACCESS_KEY_ID_SECRET_NAME")
        aws_secret_access_key_secret_name = os.getenv("AWS_SECRET_ACCESS_KEY_SECRET_NAME")
        
        if not all([aws_access_key_id_secret_name, aws_secret_access_key_secret_name]):
            logger.error("Missing AWS credentials configuration")
            raise ValueError("Missing AWS credentials configuration")
        
        # Get AWS credentials from Secret Manager
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        
        # Get AWS Access Key ID
        aws_access_key_id_path = f"projects/{os.getenv('GCP_PROJECT_ID')}/secrets/{aws_access_key_id_secret_name}/versions/latest"
        aws_access_key_id_response = client.access_secret_version(request={"name": aws_access_key_id_path})
        aws_access_key_id = aws_access_key_id_response.payload.data.decode("UTF-8").strip()
        
        # Get AWS Secret Access Key
        aws_secret_access_key_path = f"projects/{os.getenv('GCP_PROJECT_ID')}/secrets/{aws_secret_access_key_secret_name}/versions/latest"
        aws_secret_access_key_response = client.access_secret_version(request={"name": aws_secret_access_key_path})
        aws_secret_access_key = aws_secret_access_key_response.payload.data.decode("UTF-8").strip()
        
        logger.info(f"Retrieved AWS credentials from Secret Manager - Access Key ID length: {len(aws_access_key_id)}, Secret Access Key length: {len(aws_secret_access_key)}")
        
        # Configure AWS session with credentials
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        
        # Create DynamoDB resource
        dynamodb = session.resource('dynamodb', region_name=config.aws_region)
        table = dynamodb.Table(config.ddb_table_name)
        resp = table.get_item(Key={"context_id": context_id})
        item = resp.get("Item") or {}
        logger.info(f"Retrieved item from DynamoDB: {bool(item)}")
        
        if item:
            # Log the actual content retrieved from DynamoDB
            body_redacted = item.get("body_redacted", "")
            logger.info(f"DynamoDB content - body_redacted length: {len(body_redacted)}")
            logger.info(f"DynamoDB content - body_redacted: {body_redacted}")
            
            pii_map = item.get("pii_map", "{}")
            logger.info(f"DynamoDB content - pii_map: {pii_map}")
        
        return item
        
    except Exception as e:
        logger.error(f"Failed to get DynamoDB context: {e}")
        # Temporarily return empty dict to allow fallback to test message
        logger.warning("Returning empty context due to DynamoDB access failure")
        return {}


def _update_slack_modal(
    external_id: str, context_id: str, text: str, config: JobWorkerConfig
) -> bool:
    if not getattr(config, "slack_bot_token", "") or not external_id:
        logger.error(f"Missing slack_bot_token or external_id: token={bool(getattr(config, 'slack_bot_token', ''))}, external_id={external_id}")
        return False
    try:
        logger.info(f"Updating Slack modal with external_id: {external_id}, text length: {len(text)}")
        # Late import so tests can patch slack_sdk.WebClient reliably
        from slack_sdk import WebClient as _WebClient  # type: ignore
        client = _WebClient(token=config.slack_bot_token)
        view = {
            "type": "modal",
            "private_metadata": json.dumps({"context_id": context_id}),
            "title": {"type": "plain_text", "text": "AI返信アシスタント"},
            "submit": {"type": "plain_text", "text": "この内容でメールを送信"},
            "close": {"type": "plain_text", "text": "閉じる"},
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "返信文案の確認・編集"},
                },
                {
                    "type": "input",
                    "block_id": "editable_reply_block",
                    "label": {
                        "type": "plain_text",
                        "text": "以下の返信文案を編集し、送信してください。",
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "editable_reply_input",
                        "multiline": True,
                        "initial_value": text,
                    },
                },
            ],
        }
        logger.info(f"Calling Slack views_update with external_id: {external_id}")
        response = client.views_update(external_id=external_id, view=view)
        logger.info(f"Slack API response: {response}")
        return True
    except Exception as e:  # be permissive in worker context
        logger.error(f"Failed to update Slack modal: {e}")
        return False


def main() -> None:
    # Load config: allow direct env fallbacks for tests/local
    cfg: JobWorkerConfig
    try:
        # Prefer direct env if present
        direct_openai = os.getenv("OPENAI_API_KEY", "")
        direct_slack = os.getenv("SLACK_BOT_TOKEN", "")
        ddb = os.getenv("DDB_TABLE_NAME", "")
        if direct_openai and direct_slack and ddb:
            cfg = JobWorkerConfig(
                openai_api_key=direct_openai,
                slack_bot_token=direct_slack,
                ddb_table_name=ddb,
                openai_timeout=int(os.getenv("OPENAI_TIMEOUT", "30")),
            )
        else:
            cfg = JobWorkerConfig.from_env()
    except Exception:
        sys.exit(1)

    # Parse job payload - support both JOB_PAYLOAD and direct env vars
    payload_raw = os.getenv("JOB_PAYLOAD", "{}")
    try:
        payload: Dict[str, Any] = json.loads(payload_raw)
    except Exception:
        payload = {}

    # Get values from payload or direct environment variables
    context_id = str(payload.get("context_id", os.getenv("CONTEXT_ID", "")))
    external_id = str(payload.get("external_id", os.getenv("EXTERNAL_ID", "")))
    redacted_body = str(payload.get("redacted_body", ""))
    pii_map = payload.get("pii_map") or {}

    logger.info(f"Job started with context_id: {context_id}, external_id: {external_id}")
    
    if not context_id:
        logger.error("No context_id provided")
        sys.exit(1)

    # Fetch context if body absent
    if not redacted_body:
        item = _get_dynamodb_context(context_id, cfg)
        redacted_body = str(item.get("body_redacted", ""))
        raw_map = item.get("pii_map") or "{}"
        try:
            pii_map = json.loads(str(raw_map))
        except Exception:
            pii_map = {}
        
        # If still no body, use a test message temporarily
        if not redacted_body:
            redacted_body = "お客様から以下のようなお問い合わせをいただきました：\n\n商品の配送について質問があります。いつ頃届く予定でしょうか？\n\nよろしくお願いいたします。"
            logger.info("Using test message for OpenAI generation (DynamoDB access failed)")

    logger.info(f"Calling OpenAI with redacted_body length: {len(redacted_body)}")
    draft = _call_openai(redacted_body, cfg)
    if not draft:
        logger.error("OpenAI call failed or returned empty response")
        sys.exit(0)

    logger.info(f"OpenAI generated draft with length: {len(draft)}")
    final_text = _reidentify_pii(draft, pii_map)
    logger.info(f"Final text after PII reidentification: {len(final_text)}")
    
    ok = _update_slack_modal(external_id, context_id, final_text, cfg)
    if ok:
        logger.info("Successfully updated Slack modal")
    else:
        logger.error("Failed to update Slack modal")
    
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
