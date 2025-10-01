"""Cloud Run Job worker to generate AI reply and update Slack modal."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

import urllib.request

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
        table = boto3.resource("dynamodb").Table(  # type: ignore
            config.ddb_table_name
        )
        resp = table.get_item(Key={"context_id": context_id})
        return resp.get("Item") or {}
    except Exception:
        return {}


def _update_slack_modal(
    external_id: str, context_id: str, text: str, config: JobWorkerConfig
) -> bool:
    if not getattr(config, "slack_bot_token", "") or not external_id:
        return False
    try:
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
        client.views_update(external_id=external_id, view=view)
        return True
    except Exception:  # be permissive in worker context
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

    # Parse job payload
    payload_raw = os.getenv("JOB_PAYLOAD", "{}")
    try:
        payload: Dict[str, Any] = json.loads(payload_raw)
    except Exception:
        payload = {}

    context_id = str(payload.get("context_id", ""))
    external_id = str(payload.get("external_id", ""))
    redacted_body = str(payload.get("redacted_body", ""))
    pii_map = payload.get("pii_map") or {}

    if not context_id:
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

    draft = _call_openai(redacted_body, cfg)
    if not draft:
        sys.exit(0)

    final_text = _reidentify_pii(draft, pii_map)
    ok = _update_slack_modal(external_id, context_id, final_text, cfg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
