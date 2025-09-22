from __future__ import annotations

import base64
import json
from typing import Any, Dict

from common.config import load_config
from common.logging import log_error, log_info
from common.secrets import resolve_slack_credentials
from slack.signature import verify_slack_signature


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
        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
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
            return _response(200, {"ack": True})
        if event_type == "view_submission":
            log_info("received view_submission")
            return _response(200, {"response_action": "clear"})

        log_error(
            "unknown slack event type", event_type=str(event_type)
        )
        return _response(400, {"error": "unsupported"})

    # SES (S3/SES event) path - placeholder
    if "Records" in event:
        log_info("received SES/S3 record", records=len(event["Records"]))
        return _response(200, {"message": "ses event accepted"})

    return _response(400, {"error": "unrecognized event"})
