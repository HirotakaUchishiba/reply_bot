from __future__ import annotations

from typing import Any, Dict
import json
import os

from flask import Flask, request, jsonify
from slack_sdk import WebClient


app = Flask(__name__)


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.post("/async/generate")
def async_generate() -> Any:
    # Optional simple auth via static header
    expected = os.getenv("ASYNC_GENERATION_AUTH_HEADER", "")
    received = request.headers.get("Authorization", "")
    if expected and expected != received:
        return ("unauthorized", 401)

    try:
        payload: Dict[str, Any] = request.get_json(force=True) or {}
    except Exception:
        payload = {}

    context_id = str(payload.get("context_id", ""))
    external_id = str(payload.get("external_id", ""))
    redacted_body = str(payload.get("redacted_body", ""))
    pii_map = payload.get("pii_map") or {}

    # Generate text (placeholder: extend later to call OpenAI)
    draft_text = (
        "AIの返信文案（非同期生成・ダミー）\n\n" + (redacted_body[:400] or "(本文なし)")
    )

    # Optionally, re-identify here in future worker
    initial_value = draft_text

    # Update the modal using external_id via views.publish/update
    try:
        slack_token = os.getenv("SLACK_BOT_TOKEN", "")
        client = WebClient(token=slack_token)
        # views.update by external_id
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
                            "initial_value": initial_value,
                        },
                    },
                ],
            },
        )
    except Exception:
        # Log-less placeholder; Cloud Run logs will capture stack automatically
        pass

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


