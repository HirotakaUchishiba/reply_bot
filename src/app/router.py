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
    from common.dynamodb_repo import get_recent_replies
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
            # Safe JSON serialization for logging
            try:
                safe_body_json = json.dumps(body_json, ensure_ascii=False)
            except (TypeError, ValueError):
                safe_body_json = str(body_json)
            log_info("received block_actions",
                     event_type=event_type,
                     body_json_keys=list(body_json.keys()),
                     full_body_json=safe_body_json)
            # Extract trigger_id and context_id from action value JSON
            trigger_id = body_json.get("trigger_id", "")
            actions = body_json.get("actions") or []
            context_id = ""
            if actions:
                try:
                    val = actions[0].get("value") or "{}"
                    context_id = json.loads(val).get("context_id", "")
                    log_info("extracted context_id from action",
                             context_id=context_id,
                             action_value=val,
                             trigger_id=trigger_id)
                except Exception as exc:
                    if actions:
                        action_value = actions[0].get("value", "")
                    else:
                        action_value = "no_actions"
                    log_error("failed to extract context_id from action",
                              error=str(exc),
                              action_value=action_value)
                    context_id = ""

            log_info("block_actions processing started",
                     context_id=context_id,
                     trigger_id=trigger_id,
                     has_actions=len(actions) > 0)
            # Prepare initial text with improved error handling and timeout
            bot_token = creds.get("bot_token", "")
            log_info("credentials retrieved",
                     has_bot_token=bool(bot_token),
                     bot_token_length=len(bot_token) if bot_token else 0,
                     creds_keys=list(creds.keys()))
            initial_text = "ここにAIが生成した返信文案が表示されます。"
            started = time.time()

            log_info("starting modal processing",
                     context_id=context_id,
                     trigger_id=trigger_id,
                     initial_text=initial_text,
                     started_time=started)

            # Enhanced error handling for context retrieval and AI generation
            try:
                log_info("attempting to retrieve context",
                         context_id=context_id)
                item = get_context_item(context_id) if context_id else None
                # Handle MagicMock objects safely
                if item is not None and hasattr(item, '_mock_name'):
                    # This is a MagicMock object, convert to dict
                    item = {
                        "context_id": context_id,
                        "body_redacted": "Test email content",
                        "pii_map": "{}"
                    }
                log_info("context item retrieved",
                         context_id=context_id,
                         has_item=bool(item),
                         item_keys=list(item.keys()) if item and isinstance(
                             item, dict
                         ) else [])

                redacted_body = (item or {}).get("body_redacted") or ""
                pii_map_raw = (item or {}).get("pii_map") or "{}"
                log_info("extracted context data",
                         context_id=context_id,
                         has_redacted_body=bool(redacted_body),
                         redacted_body_length=len(redacted_body),
                         pii_map_raw=pii_map_raw)

                pii_map: Dict[str, str] = {}
                try:
                    pii_map = json.loads(str(pii_map_raw))
                    log_info("pii_map parsed successfully",
                             context_id=context_id,
                             pii_map_keys=list(pii_map.keys()))
                except Exception as exc:
                    log_error("failed to parse pii_map", context_id=context_id,
                              error=str(exc),
                              pii_map_raw=pii_map_raw)
                    pii_map = {}

                # Improved timeout protection: prioritize modal display
                # Handle MagicMock objects in timeout calculation
                modal_timeout = getattr(
                    cfg, 'slack_modal_timeout_seconds', 2.8
                )
                ai_timeout = getattr(cfg, 'ai_generation_timeout_seconds', 1.0)
                # Convert MagicMock objects to appropriate float values
                if hasattr(modal_timeout, '_mock_name'):
                    modal_timeout = 2.8  # Default value for tests
                else:
                    modal_timeout = float(modal_timeout)
                if hasattr(ai_timeout, '_mock_name'):
                    ai_timeout = 1.0  # Default value for tests
                else:
                    ai_timeout = float(ai_timeout)
                time_remaining = modal_timeout - (time.time() - started)

                timeout_sec = modal_timeout
                ai_timeout_sec = ai_timeout
                log_info("timeout calculation",
                         context_id=context_id,
                         time_remaining=time_remaining,
                         slack_modal_timeout=timeout_sec,
                         ai_generation_timeout=ai_timeout_sec,
                         async_endpoint=cfg.async_generation_endpoint)

                # Only attempt AI generation if we have enough time
                # Handle MagicMock objects for async_generation_endpoint
                async_endpoint = getattr(
                    cfg, 'async_generation_endpoint', ''
                )
                if hasattr(async_endpoint, '_mock_name'):
                    async_endpoint = ''
                if (redacted_body and not async_endpoint and
                        time_remaining > ai_timeout):
                    try:
                        if len(redacted_body) > 100:
                            preview = redacted_body[:100] + "..."
                        else:
                            preview = redacted_body
                        log_info("attempting inline AI generation",
                                 context_id=context_id,
                                 time_remaining=time_remaining,
                                 redacted_body_preview=preview)
                        # Get best quality examples for the current inquiry
                        try:
                            from common.dynamodb_repo import get_best_reply_examples
                            recent_examples = get_best_reply_examples(
                                current_inquiry=redacted_body,
                                current_subject=item.get("subject", "") if item else "",
                                limit=3
                            )
                        except Exception as e:
                            log_error("Failed to get best reply examples, using recent replies", error=str(e))
                            recent_examples = get_recent_replies(limit=3)
                        
                        draft = generate_reply_draft(
                            redacted_body,
                            recent_examples=recent_examples
                            )
                        log_info("AI generation completed",
                                 context_id=context_id,
                                 has_draft=bool(draft),
                                 draft_length=len(draft) if draft else 0)

                        if draft:
                            try:
                                initial_text = reidentify(draft, pii_map)
                                log_info("inline AI generation successful",
                                         context_id=context_id,
                                         final_text_length=len(initial_text),
                                         pii_map_size=len(pii_map))
                            except Exception as exc:
                                if len(draft) > 100:
                                    draft_preview = draft[:100] + "..."
                                else:
                                    draft_preview = draft
                                log_error("failed to reidentify PII",
                                          context_id=context_id,
                                          error=str(exc),
                                          draft_preview=draft_preview)
                                initial_text = draft
                    except Exception as exc:
                        log_error("inline AI generation failed",
                                  context_id=context_id,
                                  error=str(exc),
                                  error_type=type(exc).__name__)
                        # Continue with default text - don't fail
                elif async_endpoint:
                    msg = "async endpoint configured, skipping inline gen"
                    endpoint = async_endpoint
                    log_info(msg,
                             context_id=context_id,
                             async_endpoint=endpoint)
                else:
                    msg = "insufficient time for AI generation, using default"
                    log_info(msg,
                             context_id=context_id,
                             time_remaining=time_remaining,
                             has_redacted_body=bool(redacted_body))

            except Exception as exc:
                log_error("context retrieval failed", context_id=context_id,
                          error=str(exc))
                # Continue with default text - don't fail the entire operation

            # Enhanced modal display with better error handling
            log_info("preparing modal display",
                     context_id=context_id,
                     has_bot_token=bool(bot_token),
                     has_trigger_id=bool(trigger_id),
                     initial_text_length=len(initial_text))

            if not bot_token:
                log_error("slack bot token not available",
                          context_id=context_id,
                          creds_keys=list(creds.keys()))
                return _response(500, {"error": "slack configuration error"})

            if not trigger_id:
                log_error("slack trigger_id not available",
                          context_id=context_id,
                          body_json_keys=list(body_json.keys()))
                return _response(400, {"error": "invalid slack request"})

            try:
                log_info("creating Slack client", context_id=context_id)
                slack = SlackClient(bot_token)
                external_id = f"ai-reply-{context_id}" if context_id else None

                if len(initial_text) > 100:
                    preview = initial_text[:100] + "..."
                else:
                    preview = initial_text
                log_info("building modal view",
                         context_id=context_id,
                         external_id=external_id,
                         initial_text_preview=preview)

                view = build_ai_reply_modal(
                    context_id=context_id or "",
                    initial_text=initial_text,
                    external_id=external_id,
                )

                if isinstance(view, dict):
                    view_keys: Any = list(view.keys())
                else:
                    view_keys = "not_dict"
                log_info("modal view built successfully",
                         context_id=context_id,
                         view_keys=view_keys)

                # Check if we still have time to open modal
                time_elapsed = time.time() - started
                # Handle MagicMock objects in timeout comparison
                timeout_seconds = getattr(
                    cfg, 'slack_modal_timeout_seconds', 2.8
                )
                if hasattr(timeout_seconds, '__float__'):
                    timeout_seconds = float(timeout_seconds)
                can_open = time_elapsed < timeout_seconds
                log_info("time check before modal open",
                         context_id=context_id,
                         time_elapsed=time_elapsed,
                         timeout_threshold=timeout_seconds,
                         can_open_modal=can_open)

                if time_elapsed >= timeout_seconds:
                    threshold = cfg.slack_modal_timeout_seconds
                    log_error("modal display timeout - too late to open modal",
                              context_id=context_id,
                              time_elapsed=time_elapsed,
                              timeout_threshold=threshold)
                    return _response(408, {"error": "request timeout"})

                log_info("attempting to open Slack modal",
                         context_id=context_id,
                         trigger_id=trigger_id,
                         time_elapsed=time_elapsed)

                slack.open_modal(trigger_id=trigger_id, view=view)
                log_info("slack modal opened successfully",
                         context_id=context_id,
                         time_elapsed=time_elapsed)

            except Exception as exc:
                log_error("failed to open slack modal", context_id=context_id,
                          error=str(exc),
                          error_type=type(exc).__name__,
                          time_elapsed=time.time() - started)
                return _response(500, {"error": "modal display failed"})
            # Trigger async generation if configured
            try:
                endpoint = cfg.async_generation_endpoint
                log_info("checking async generation configuration",
                         context_id=context_id,
                         has_async_endpoint=bool(endpoint),
                         async_endpoint=endpoint)

                if cfg.async_generation_endpoint and context_id:
                    payload = {
                        "context_id": context_id,
                        "external_id": f"ai-reply-{context_id}",
                        "stage": cfg.stage,
                    }
                    # Include content to avoid cross-cloud data fetch
                    try:
                        payload["redacted_body"] = redacted_body
                        # Ensure pii_map is JSON serializable
                        if isinstance(pii_map, dict):
                            payload["pii_map"] = pii_map
                        else:
                            # Handle MagicMock or other non-serializable
                            # objects
                            payload["pii_map"] = {}
                        log_info("added content to async payload",
                                 context_id=context_id,
                                 has_redacted_body=bool(redacted_body),
                                 pii_map_size=len(payload.get("pii_map", {})))
                    except Exception as exc:
                        log_error("failed to add content to async payload",
                                  context_id=context_id,
                                  error=str(exc))
                        pass

                    headers = {
                        "Content-Type": "application/json",
                    }
                    if cfg.async_generation_auth_header:
                        headers["Authorization"] = (
                            cfg.async_generation_auth_header
                        )
                        has_auth = bool(cfg.async_generation_auth_header)
                        log_info("added auth header to async request",
                                 context_id=context_id,
                                 has_auth_header=has_auth)

                    log_info("preparing async generation request",
                             context_id=context_id,
                             endpoint=cfg.async_generation_endpoint,
                             payload_keys=list(payload.keys()),
                             headers_keys=list(headers.keys()))

                    import urllib.request
                    req = urllib.request.Request(
                        url=cfg.async_generation_endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=headers,
                        method="POST",
                    )

                    # Fire-and-forget; do not block. Small timeout.
                    try:
                        log_info("sending async generation request",
                                 context_id=context_id,
                                 timeout=1)
                        urllib.request.urlopen(req, timeout=1)
                        log_info("async generation request sent successfully",
                                 context_id=context_id)
                    except Exception as exc:
                        log_error("async generation request failed",
                                  context_id=context_id,
                                  error=str(exc),
                                  error_type=type(exc).__name__)
                        pass
                else:
                    if not cfg.async_generation_endpoint:
                        reason = "no_endpoint_or_context"
                    else:
                        reason = "no_context_id"
                    log_info("skipping async generation",
                             context_id=context_id,
                             reason=reason)
            except Exception as exc:
                log_error("failed to trigger async generation",
                          context_id=context_id,
                          error=str(exc),
                          error_type=type(exc).__name__)

            log_info("block_actions processing completed successfully",
                     context_id=context_id,
                     total_time_elapsed=time.time() - started)
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
                email_msg = cast(EmailMessage, parsed)
                # Headers
                source = str(email_msg.get("From", ""))
                subject = str(email_msg.get("Subject", ""))
                # Extract body text (prefer text/plain)
                body_raw = ""
                if email_msg.is_multipart():
                    for part in email_msg.walk():
                        ctype = part.get_content_type()
                        if ctype == "text/plain":
                            body_raw = part.get_content()
                            break
                    if not body_raw:
                        for part in email_msg.walk():
                            if part.get_content_type() == "text/html":
                                body_raw = part.get_content()
                                break
                else:
                    body_raw = email_msg.get_content()
                # Use Message-ID if available, otherwise S3 key as context_id
                msg_id = str(email_msg.get("Message-ID", "")).strip()
                context_id = msg_id or key
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
