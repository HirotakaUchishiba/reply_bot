from __future__ import annotations

from typing import Any, Dict
import json
import os
import urllib.request
import logging
import sys

from config import JobWorkerConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _call_openai(redacted_body: str, config: JobWorkerConfig) -> str:
    """Call OpenAI API to generate reply draft."""
    if not redacted_body:
        logger.warning("Empty redacted body provided")
        return ""
    
    if not config.openai_api_key:
        logger.error("OpenAI API key not provided")
        return ""
    
    lines = [
        "あなたは日本語のCS担当者です。以下の問い合わせに対し、",
        "丁寧で簡潔な返信文案を日本語で作成してください。",
        "- 会社のブランドトーンに合う丁寧語",
        "- 不確実な点は確認依頼として記載",
        "- 箇条書き可",
        "- 件名行は不要",
        "",
        "問い合わせ本文（機微情報はプレースホルダーに置換済み）：",
        redacted_body,
        "",
    ]
    prompt = "\n".join(lines)
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "max_tokens": 300,
    }
    
    try:
        req = urllib.request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=config.openai_timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        data: Dict[str, Any] = json.loads(raw)
        choices = data.get("choices") or []
        if not choices:
            logger.error("No choices returned from OpenAI API")
            return ""
        message = choices[0].get("message", {})
        content = (message or {}).get("content", "")
        result = str(content or "").strip()
        logger.info(f"OpenAI generation completed, length: {len(result)}")
        return result
    except Exception as exc:
        logger.error(f"OpenAI API call failed: {exc}")
        return ""


def _reidentify_pii(text: str, pii_map: Dict[str, str]) -> str:
    """Restore PII placeholders with original values."""
    if not pii_map:
        return text
    
    result = text
    for placeholder, original in pii_map.items():
        result = result.replace(placeholder, original)
    return result


def _get_dynamodb_context(context_id: str, config: JobWorkerConfig) -> Dict[str, Any]:
    """Retrieve context from DynamoDB via AWS API."""
    if not context_id:
        return {}
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name=config.aws_region)
        table = dynamodb.Table(config.ddb_table_name)
        
        # Get item
        response = table.get_item(Key={'context_id': context_id})
        item = response.get('Item', {})
        
        if item:
            logger.info(f"Retrieved context for {context_id}")
        else:
            logger.warning(f"No context found for {context_id}")
        
        return item
    except Exception as exc:
        logger.error(f"Failed to retrieve DynamoDB context: {exc}")
        return {}


def _update_slack_modal(external_id: str, context_id: str, final_text: str, config: JobWorkerConfig) -> bool:
    """Update Slack modal with generated text."""
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        if not config.slack_bot_token:
            logger.error("SLACK_BOT_TOKEN not configured")
            return False
        
        if not external_id:
            logger.error("external_id not provided")
            return False
        
        client = WebClient(token=config.slack_bot_token)
        
        view = {
            "type": "modal",
            "external_id": external_id,
            "callback_id": "ai_reply_modal_submission",
            "title": {"type": "plain_text", "text": "AI返信アシスタント"},
            "submit": {"type": "plain_text", "text": "この内容でメールを送信"},
            "close": {"type": "plain_text", "text": "閉じる"},
            "private_metadata": json.dumps({"context_id": context_id}),
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "返信文案の確認・編集",
                    },
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
                        "initial_value": final_text,
                    },
                },
            ],
        }
        
        client.views_update(external_id=external_id, view=view)
        logger.info(f"Successfully updated Slack modal for {external_id}")
        return True
        
    except SlackApiError as exc:
        logger.error(f"Slack API error: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Failed to update Slack modal: {exc}")
        return False


def main() -> None:
    """Main entry point for Cloud Run Job worker."""
    logger.info("Starting Cloud Run Job worker")
    
    try:
        config = JobWorkerConfig.from_env()
    except ValueError as exc:
        logger.error(f"Configuration error: {exc}")
        sys.exit(1)
    
    # Expect JSON payload via env (e.g., Cloud Run job args -> env)
    payload_raw = os.getenv("JOB_PAYLOAD", "{}")
    try:
        payload: Dict[str, Any] = json.loads(payload_raw)
    except Exception as exc:
        logger.error(f"Failed to parse JOB_PAYLOAD: {exc}")
        payload = {}

    context_id = str(payload.get("context_id", ""))
    external_id = str(payload.get("external_id", ""))
    
    logger.info(f"Processing job for context_id: {context_id}, external_id: {external_id}")
    
    if not context_id:
        logger.error("context_id is required")
        sys.exit(1)
    
    if not external_id:
        logger.error("external_id is required")
        sys.exit(1)

    # Get context from DynamoDB if not provided in payload
    redacted_body = str(payload.get("redacted_body", ""))
    pii_map: Dict[str, str] = payload.get("pii_map") or {}
    
    if not redacted_body:
        logger.info("Retrieving context from DynamoDB")
        context_item = _get_dynamodb_context(context_id, config)
        if context_item:
            redacted_body = str(context_item.get("body_redacted", ""))
            pii_map_raw = str(context_item.get("pii_map", "{}"))
            try:
                pii_map = json.loads(pii_map_raw)
            except Exception:
                pii_map = {}
        else:
            logger.error("Failed to retrieve context from DynamoDB")
            sys.exit(1)

    if not redacted_body:
        logger.error("No redacted body available for generation")
        sys.exit(1)

    # Generate reply with OpenAI
    logger.info("Generating reply with OpenAI")
    draft = _call_openai(redacted_body, config)
    
    if not draft:
        logger.error("Failed to generate reply draft")
        draft = "申し訳ございませんが、返信文案の生成に失敗しました。手動で入力してください。"
    
    # Restore PII in the generated text
    final_text = _reidentify_pii(draft, pii_map)
    logger.info(f"Final text length: {len(final_text)}")

    # Update Slack modal
    logger.info("Updating Slack modal")
    success = _update_slack_modal(external_id, context_id, final_text, config)
    
    if success:
        logger.info("Job completed successfully")
        sys.exit(0)
    else:
        logger.error("Job failed to update Slack modal")
        sys.exit(1)


if __name__ == "__main__":
    main()


