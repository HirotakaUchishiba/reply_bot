from __future__ import annotations

from typing import Any, Dict

import base64
import json

from common.config import load_config
from common.logging import log_error, log_info
from common.secrets import resolve_gmail_oauth, clear_secrets_cache
from common.dynamodb_repo import put_context_item
from common.pii import redact_and_map
from slack.client import SlackClient, build_new_email_notification


def _get_gmail_service(creds_dict: Dict[str, str]):
    # Import Gmail SDK lazily to avoid import errors in environments
    # where libs are not installed (e.g., certain CI or lint contexts).
    from google.oauth2.credentials import (  # type: ignore[import-not-found]
        Credentials as GoogleCredentials,
    )
    from googleapiclient.discovery import (  # type: ignore[import-not-found]
        build as google_build,
    )

    creds = GoogleCredentials(
        None,
        refresh_token=creds_dict.get("refresh_token", ""),
        client_id=creds_dict.get("client_id", ""),
        client_secret=creds_dict.get("client_secret", ""),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )
    return google_build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False,
    )


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    cfg = load_config()
    try:
        clear_secrets_cache()
        secret_arn = cfg.gmail_oauth_secret_arn  # type: ignore[attr-defined]
        gmail_creds = resolve_gmail_oauth(secret_arn)
    except Exception as exc:
        log_error("missing gmail secrets", error=str(exc))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration"}),
        }

    try:
        service = _get_gmail_service(gmail_creds)
        # UNREAD を最新から少数だけ取得
        msgs_resp = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread", maxResults=5)
            .execute()
        )
        messages = msgs_resp.get("messages", [])
        count = 0
        for m in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=m["id"], format="full")
                .execute()
            )
            headers = {
                h["name"].lower(): h.get("value", "")
                for h in msg.get("payload", {}).get("headers", [])
            }
            subject = headers.get("subject", "")
            sender = headers.get("from", "")
            parts = msg.get("payload", {}).get("parts", [])
            body_raw = ""
            for p in parts or []:
                if p.get("mimeType") in ("text/plain", "text/html"):
                    data = p.get("body", {}).get("data", "")
                    if data:
                        body_raw = base64.urlsafe_b64decode(data).decode(
                            "utf-8", errors="ignore"
                        )
                        break
            redacted, pii_map = redact_and_map(body_raw)
            context_id = msg.get("id", "")
            put_context_item(
                {
                    "context_id": context_id,
                    "sender_email": sender,
                    "subject": subject,
                    "body_raw": body_raw,
                    "body_redacted": redacted,
                    "pii_map": json.dumps(pii_map, ensure_ascii=False),
                }
            )
            # Slack 通知
            try:
                preview = (
                    (redacted or body_raw or "").strip().replace("\r", "")
                )
                if len(preview) > 400:
                    preview = preview[:400] + "…"
                blocks = build_new_email_notification(
                    context_id=context_id,
                    sender=sender,
                    subject=subject,
                    preview_text=preview or "(本文なし)",
                )
                # Slack トークンは既存の resolver を再利用
                from common.secrets import resolve_slack_credentials

                clear_secrets_cache()
                creds = resolve_slack_credentials(
                    cfg.slack_signing_secret_arn,
                    cfg.slack_app_secret_arn,
                )
                bot_token = creds.get("bot_token", "")
                if bot_token and cfg.slack_channel_id:
                    SlackClient(bot_token).post_message(
                        channel=cfg.slack_channel_id,
                        text=f"新しい問い合わせ: {subject}",
                        blocks=blocks,
                    )
                count += 1
            except Exception as exc:
                log_error("slack notify failed", error=str(exc))
        log_info("gmail poll completed", fetched=count)
        return {"statusCode": 200, "body": json.dumps({"fetched": count})}
    except Exception as exc:
        log_error("gmail poll failed", error=str(exc))
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}
