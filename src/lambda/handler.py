import json
import os
from typing import Any, Dict


def _json_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entrypoint.

    Placeholder handler for initial scaffolding. Will be expanded to route
    SES events and Slack interactions per the design documents.
    """

    request_id = getattr(context, "aws_request_id", None) if context else None
    return _json_response(
        200,
        {
            "message": "ok",
            "request_id": request_id,
            "environment": {"stage": os.getenv("STAGE", "dev")},
            "event_type": type(event).__name__,
        },
    )


