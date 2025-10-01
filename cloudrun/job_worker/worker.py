from __future__ import annotations

from typing import Any, Dict
import json
import os
import urllib.request


def _call_openai(redacted_body: str, api_key: str) -> str:
    if not redacted_body:
        return ""
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": (
                    "あなたは日本語のCS担当者です。以下の問い合わせに対し、"
                    "丁寧で簡潔な返信文案を日本語で作成してください。\n\n" + redacted_body
                ),
            }
        ],
        "max_tokens": 300,
    }
    req = urllib.request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    data: Dict[str, Any] = json.loads(raw)
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = (message or {}).get("content", "")
    return str(content or "").strip()


def main() -> None:
    # Expect JSON payload via env (e.g., Cloud Run job args -> env)
    payload_raw = os.getenv("JOB_PAYLOAD", "{}")
    try:
        payload: Dict[str, Any] = json.loads(payload_raw)
    except Exception:
        payload = {}

    context_id = str(payload.get("context_id", ""))
    external_id = str(payload.get("external_id", ""))
    redacted_body = str(payload.get("redacted_body", ""))
    pii_map: Dict[str, str] = payload.get("pii_map") or {}

    # OpenAI
    api_key = os.getenv("OPENAI_API_KEY", "")
    draft = _call_openai(redacted_body, api_key) if api_key else ""
    final_text = draft or ""

    # Slack update
    try:
        from slack_sdk import WebClient  # lazy import

        token = os.getenv("SLACK_BOT_TOKEN", "")
        if token and external_id:
            client = WebClient(token=token)
            client.views_update(
                external_id=external_id,
                view={
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
                },
            )
    except Exception:
        pass


if __name__ == "__main__":
    main()


