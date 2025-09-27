from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, Optional

import boto3


@lru_cache(maxsize=32)
def get_secret_string(secret_arn: str) -> str:
    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=secret_arn)
    if "SecretString" in resp:
        return str(resp["SecretString"])
    # Binary secret not supported in this app
    raise ValueError("SecretString not found for ARN")


def clear_secrets_cache() -> None:
    """Clear the secrets cache to force fresh retrieval."""
    get_secret_string.cache_clear()


def get_secret_json(secret_arn: str) -> Dict[str, Any]:
    raw = get_secret_string(secret_arn)
    return json.loads(raw)  # type: ignore[no-any-return]


def resolve_slack_credentials(
    signing_secret_arn: Optional[str], app_secret_arn: Optional[str]
) -> Dict[str, str]:
    # Prefer JSON secret containing both
    if app_secret_arn:
        data = get_secret_json(app_secret_arn)
        signing = data.get("signing_secret")
        bot_token = data.get("bot_token")
        if not signing or not bot_token:
            raise ValueError(
                "Slack app secret JSON must include 'signing_secret' "
                "and 'bot_token'"
            )
        return {"signing_secret": signing, "bot_token": bot_token}
    if signing_secret_arn:
        signing = get_secret_string(signing_secret_arn)
        return {"signing_secret": signing}
    raise ValueError("Slack secrets are not configured")


def resolve_openai_api_key(openai_secret_arn: Optional[str]) -> str:
    if not openai_secret_arn:
        raise ValueError("OPENAI_API_KEY secret ARN not provided")
    return get_secret_string(openai_secret_arn)
