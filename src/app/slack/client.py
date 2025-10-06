from __future__ import annotations

from typing import Any, Dict
import json
import time

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

try:
    from common.logging import log_error, log_info
except ImportError:
    from .common.logging import log_error, log_info


class SlackClient:
    def __init__(self, bot_token: str) -> None:
        self._client = WebClient(token=bot_token)

    def open_modal(self, trigger_id: str, view: Dict[str, Any]) -> None:
        """
        Open Slack modal with enhanced error handling and timeout protection.
        Slack requires views.open within 3 seconds of interaction.
        """
        start_time = time.time()
        try:
            log_info("attempting to open slack modal", 
                     trigger_id=trigger_id,
                     view_type=view.get("type", "unknown"),
                     view_blocks_count=len(view.get("blocks", [])) if isinstance(view.get("blocks"), list) else 0,
                     has_private_metadata=bool(view.get("private_metadata")))
            
            log_info("calling Slack API views.open", 
                     trigger_id=trigger_id,
                     view_keys=list(view.keys()) if isinstance(view, dict) else "not_dict")
            
            self._client.views_open(trigger_id=trigger_id, view=view)
            elapsed = time.time() - start_time
            log_info("slack modal opened successfully", 
                     trigger_id=trigger_id,
                     elapsed=elapsed,
                     api_call_successful=True)
        except SlackApiError as e:
            elapsed = time.time() - start_time
            error_code = getattr(e, 'response', {}).get('error', 'unknown')
            error_response = getattr(e, 'response', {})
            log_error("slack API error when opening modal",
                      trigger_id=trigger_id,
                      error=str(e),
                      error_code=error_code,
                      error_response=error_response,
                      elapsed=elapsed,
                      api_call_successful=False)
            raise
        except Exception as e:
            elapsed = time.time() - start_time
            log_error("unexpected error when opening modal",
                      trigger_id=trigger_id,
                      error=str(e),
                      error_type=type(e).__name__,
                      elapsed=elapsed,
                      api_call_successful=False)
            raise

    def post_message(
        self, channel: str, text: str, blocks: Dict[str, Any] | None = None
    ) -> None:
        kwargs: Dict[str, Any] = {"channel": channel, "text": text}
        if blocks is not None:
            kwargs["blocks"] = blocks
        self._client.chat_postMessage(**kwargs)


def build_ai_reply_modal(
    context_id: str, initial_text: str, external_id: str | None = None
) -> Dict[str, Any]:
    # Block Kit modal per design docs with fixed IDs
    view: Dict[str, Any] = {
        "type": "modal",
        "callback_id": "ai_reply_modal_submission",
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
                    "initial_value": initial_text,
                },
            },
        ],
    }
    # Allow async updates: attach external_id so we can update this view later
    if external_id:
        view["external_id"] = external_id
    return view


def build_new_email_notification(
    context_id: str,
    sender: str,
    subject: str,
    preview_text: str,
) -> Any:
    # Block Kit message for new email notification with action button
    try:
        value_json = json.dumps({"context_id": context_id})
    except Exception:
        value_json = "{}"
    blocks: Any = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "新しい問い合わせが届きました"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*From:* {sender}"},
                {"type": "mrkdwn", "text": f"*Subject:* {subject}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": preview_text,
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "返信文を生成する"},
                    "style": "primary",
                    "action_id": "generate_reply_action",
                    "value": value_json,
                }
            ],
        },
    ]
    return blocks
