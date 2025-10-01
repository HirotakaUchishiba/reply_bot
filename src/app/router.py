from __future__ import annotations

import base64
import json
from typing import Any, Dict, cast
import time

from urllib.parse import parse_qs
from urllib.parse import unquote_plus
import boto3
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage

try:
    # Lambda環境用の絶対インポート
    from common.config import load_config
    from common.logging import log_error, log_info
    from common.secrets import resolve_slack_credentials, clear_secrets_cache
    from common.dynamodb_repo import get_context_item, put_context_item
    from common.ses_email import send_email
    from slack.signature import verify_slack_signature  # type: ignore
    from slack.client import (
        SlackClient,
        build_ai_reply_modal,
        build_new_email_notification,
    )
    from common.pii import redact_and_map, reidentify
except ImportError:
    # テスト環境用の相対インポート
    from .common.config import load_config
    from .common.logging import log_error, log_info
    from .common.secrets import resolve_slack_credentials, clear_secrets_cache
    from .common.dynamodb_repo import get_context_item, put_context_item
    from .common.ses_email import send_email
    from .slack.signature import verify_slack_signature
    from .slack.client import (
        SlackClient,
        build_ai_reply_modal,
        build_new_email_notification,
    )
    from .common.pii import redact_and_map, reidentify

# OpenAI クライアントは任意依存のため、個別にフォールバックを用意
try:  # pragma: no cover - import-time guard
    from common.openai_client import generate_reply_draft  # type: ignore
except Exception:  # pragma: no cover - optional dependency missing
    def generate_reply_draft(
        *args: Any, **kwargs: Any
    ) -> str:  # type: ignore[no-redef]
        log_info(
            "OpenAI client not available, skipping reply generation."
        )
        return ""


def _response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def handle_event(event: Dict[str, Any]) -> Dict[str, Any]:
    cfg = load_config()

    # API Gateway v2 (HTTP API) path
    if "requestContext" in event and "http" in event["requestContext"]:
        is_base64 = event.get("isBase64Encoded", False)
        raw_body = event.get("body") or ""
        body_bytes = (
            base64.b64decode(raw_body)
            if is_base64
            else raw_body.encode("utf-8")
        )

        # Slack signature verification
        headers = {
            k.lower(): v for k, v in (event.get("headers") or {}).items()
        }
        ts = headers.get("x-slack-request-timestamp", "0")
        sig = headers.get("x-slack-signature", "")

        try:
            # Clear secrets cache to ensure fresh token retrieval
            clear_secrets_cache()
            creds = resolve_slack_credentials(
                cfg.slack_signing_secret_arn, cfg.slack_app_secret_arn
            )
            signing_secret = creds["signing_secret"]
        except Exception as exc:
            log_error("missing slack secrets", error=str(exc))
            return _response(500, {"error": "server configuration"})

        if not verify_slack_signature(signing_secret, ts, sig, body_bytes):
            log_error("slack signature verification failed")
            return _response(401, {"error": "unauthorized"})

        # Slack URL verification challenge support
        body_text = body_bytes.decode("utf-8")
        content_type = headers.get("content-type", "")
        body_json: Dict[str, Any] = {}
        # Slack Interactivity: application/x-www-form-urlencoded with 'payload'
        if "application/x-www-form-urlencoded" in content_type:
            form = parse_qs(body_text)
            payload_raw = (form.get("payload") or ["{}"])[0]
            try:
                body_json = json.loads(payload_raw)
            except Exception:
                body_json = {}
        else:
            try:
                body_json = json.loads(body_text)
            except Exception:
                body_json = {}

        if (
            body_json.get("type") == "url_verification"
            and body_json.get("challenge")
        ):
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "text/plain"},
                "body": body_json["challenge"],
            }

        # Distinguish block_actions vs view_submission
        event_type = body_json.get("type")
        if event_type == "block_actions":
            log_info("received block_actions")
            # Extract trigger_id and context_id from action value JSON
            trigger_id = body_json.get("trigger_id", "")
            actions = body_json.get("actions") or []
            context_id = ""
            if actions:
                try:
                    val = actions[0].get("value") or "{}"
                    context_id = json.loads(val).get("context_id", "")
                except Exception:
                    context_id = ""
            # Prepare initial text. If async endpoint is configured, we won't
            # block beyond a small budget.
            bot_token = creds.get("bot_token", "")
            initial_text = "ここにAIが生成した返信文案が表示されます。"
            started = time.time()
            try:
                item = get_context_item(context_id) if context_id else None
                redacted_body = (item or {}).get("body_redacted") or ""
                pii_map_raw = (item or {}).get("pii_map") or "{}"
                pii_map: Dict[str, str] = {}
                try:
                    pii_map = json.loads(str(pii_map_raw))
                except Exception:
                    pii_map = {}
                # Do quick inline generation only when async endpoint is not
                # set and within a tight time budget.
                if (
                    redacted_body
                    and not cfg.async_generation_endpoint
                    and (time.time() - started) < 3.0
                ):
                    try:
                        draft = generate_reply_draft(redacted_body)
                    except Exception as exc:
                        log_error("openai generation failed", error=str(exc))
                        draft = ""
                    if draft:
                        try:
                            initial_text = reidentify(draft, pii_map)
                        except Exception:
                            initial_text = draft
            except Exception as exc:
                log_error("prefill draft failed", error=str(exc))

            # Open modal
            if bot_token and trigger_id:
                try:
                    slack = SlackClient(bot_token)
                    external_id = (
                        f"ai-reply-{context_id}" if context_id else None
                    )
                    view = build_ai_reply_modal(
                        context_id=context_id or "",
                        initial_text=initial_text,
                        external_id=external_id,
                    )
                    slack.open_modal(trigger_id=trigger_id, view=view)
                except Exception as exc:
                    log_error("failed to open slack modal", error=str(exc))
            # Trigger async generation if configured
            try:
                if cfg.async_generation_endpoint and context_id:
                    payload = {
                        "context_id": context_id,
                        "external_id": f"ai-reply-{context_id}",
                        "stage": cfg.stage,
                    }
                    # Include content to avoid cross-cloud data fetch
                    try:
                        payload["redacted_body"] = redacted_body
                        payload["pii_map"] = pii_map
                    except Exception:
                        pass
                    headers = {
                        "Content-Type": "application/json",
                    }
                    if cfg.async_generation_auth_header:
                        headers["Authorization"] = (
                            cfg.async_generation_auth_header
                        )
                    import urllib.request
                    req = urllib.request.Request(
                        url=cfg.async_generation_endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=headers,
                        method="POST",
                    )
                    # Fire-and-forget; do not block. Small timeout.
                    try:
                        urllib.request.urlopen(req, timeout=1)
                    except Exception:
                        pass
            except Exception as exc:
                log_error("failed to trigger async generation", error=str(exc))

            return _response(200, {"ack": True})
        if event_type == "view_submission":
            log_info("received view_submission")
            # Extract context_id from private_metadata
            private_metadata = body_json.get("view", {}).get(
                "private_metadata", "{}"
            )
            try:
                meta = json.loads(private_metadata)
            except Exception:
                meta = {}
            context_id = meta.get("context_id", "")

            # Extract edited text
            values = body_json.get("view", {}).get("state", {}).get(
                "values", {}
            )
            edited_text = (
                values.get("editable_reply_block", {})
                .get("editable_reply_input", {})
                .get("value", "")
            )

            # Fetch context from DDB
            item = get_context_item(context_id) if context_id else None
            if not item:
                log_error(
                    "context not found or missing", context_id=context_id
                )
                return _response(200, {"response_action": "clear"})

            recipient = item.get("sender_email") or item.get("to") or ""
            subject = item.get("subject") or ""

            # Send email via SES
            try:
                send_email(
                    sender=cfg.sender_email_address,
                    to_addresses=[recipient],
                    subject=subject,
                    body=edited_text,
                )
            except Exception as exc:
                log_error("ses send_email failed", error=str(exc))

            # Post Slack confirmation
            try:
                # Clear secrets cache to ensure fresh token retrieval
                clear_secrets_cache()
                bot_token = (
                    resolve_slack_credentials(
                        cfg.slack_signing_secret_arn,
                        cfg.slack_app_secret_arn,
                    ).get("bot_token", "")
                )
                if bot_token and cfg.slack_channel_id:
                    SlackClient(bot_token).post_message(
                        channel=cfg.slack_channel_id,
                        text="返信が完了しました",
                    )
            except Exception as exc:
                log_error(
                    "slack post confirmation failed", error=str(exc)
                )

            return _response(200, {"response_action": "clear"})

        log_error("unknown slack event type", event_type=str(event_type))
        return _response(400, {"error": "unsupported"})

    # S3 (SES inbound) event path: fetch raw email from S3,
    # parse, persist, then notify via Slack
    if "Records" in event:
        try:
            record = (event.get("Records") or [])[0]
            # If S3 event
            if "s3" in record:
                s3_info = record.get("s3", {})
                bucket = (s3_info.get("bucket") or {}).get("name", "")
                key_enc = (s3_info.get("object") or {}).get("key", "")
                key = unquote_plus(key_enc)
                s3 = boto3.client("s3")
                obj = s3.get_object(Bucket=bucket, Key=key)
                raw_bytes = obj["Body"].read()
                parser = BytesParser(
                    policy=policy.default  # type: ignore[arg-type]
                )
                parsed = parser.parsebytes(raw_bytes)
                msg = cast(EmailMessage, parsed)
                # Headers
                source = str(msg.get("From", ""))
                subject = str(msg.get("Subject", ""))
                # Extract body text (prefer text/plain)
                body_raw = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        if ctype == "text/plain":
                            body_raw = part.get_content()
                            break
                    if not body_raw:
                        for part in msg.walk():
                            if part.get_content_type() == "text/html":
                                body_raw = part.get_content()
                                break
                else:
                    body_raw = msg.get_content()
                # Use Message-ID if available, otherwise S3 key as context_id
                context_id = str(msg.get("Message-ID", "")).strip() or key
            else:
                # Backward compatibility: legacy SES direct event
                # (not used when S3 notifications enabled)
                mail = (record.get("ses") or {}).get("mail") or {}
                source = mail.get("source", "")
                subject = mail.get("commonHeaders", {}).get("subject", "")
                body_raw = (record.get("body") or "")
                context_id = mail.get("messageId", "")
            redacted, pii_map = redact_and_map(body_raw)
            item = {
                "context_id": context_id,
                "sender_email": source,
                "subject": subject,
                "body_raw": body_raw,
                "body_redacted": redacted,
                "pii_map": json.dumps(pii_map, ensure_ascii=False),
            }
            put_context_item(item)
            log_info("context saved", context_id=context_id)

            # Slack notify with new email details
            try:
                # Clear secrets cache to ensure fresh token retrieval
                clear_secrets_cache()
                creds = resolve_slack_credentials(
                    cfg.slack_signing_secret_arn,
                    cfg.slack_app_secret_arn,
                )
                bot_token = creds.get("bot_token", "")
                if bot_token and cfg.slack_channel_id:
                    text_for_preview = (redacted or body_raw or "")
                    preview = text_for_preview.strip().replace("\r", "")
                    if len(preview) > 400:
                        preview = preview[:400] + "…"
                    blocks = build_new_email_notification(
                        context_id=context_id,
                        sender=source,
                        subject=subject,
                        preview_text=(preview or "(本文なし)"),
                    )
                    SlackClient(bot_token).post_message(
                        channel=cfg.slack_channel_id,
                        text=f"新しい問い合わせ: {subject}",
                        blocks=blocks,
                    )
            except Exception as exc:
                log_error("slack notify failed", error=str(exc))
        except Exception as exc:
            log_error("failed to process ses event", error=str(exc))
        return _response(200, {"message": "ses event accepted"})

    return _response(400, {"error": "unrecognized event"})
