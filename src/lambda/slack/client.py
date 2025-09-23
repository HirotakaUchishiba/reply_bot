from __future__ import annotations

from typing import Any, Dict
import json

from slack_sdk import WebClient


class SlackClient:
    def __init__(self, bot_token: str) -> None:
        self._client = WebClient(token=bot_token)

    def open_modal(self, trigger_id: str, view: Dict[str, Any]) -> None:
        # Slack requires views.open within 3 seconds of interaction
        self._client.views_open(trigger_id=trigger_id, view=view)

    def post_message(
        self, channel: str, text: str, blocks: Dict[str, Any] | None = None
    ) -> None:
        kwargs: Dict[str, Any] = {"channel": channel, "text": text}
        if blocks is not None:
            kwargs["blocks"] = blocks
        self._client.chat_postMessage(**kwargs)


def build_ai_reply_modal(context_id: str, initial_text: str) -> Dict[str, Any]:
    # Block Kit modal per design docs with fixed IDs
    return {
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
