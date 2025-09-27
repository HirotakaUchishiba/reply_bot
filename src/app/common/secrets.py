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


def resolve_slack_credentials(signing_secret_arn: str, app_secret_arn: str) -> Dict[str, str]:
    signing_secret = get_secret_string(signing_secret_arn)
    app_secret = get_secret_json(app_secret_arn)
    return {
        "bot_token": app_secret.get("bot_token", ""),
        "signing_secret": signing_secret,
    }


def resolve_openai_api_key(api_key_secret_arn: str) -> str:
    return get_secret_string(api_key_secret_arn)


# Gmail OAuth secrets: expected JSON structure in Secrets Manager
# {
#   "client_id": "...",
#   "client_secret": "...",
#   "refresh_token": "..."
# }

def resolve_gmail_oauth(app_secret_arn: str) -> Dict[str, str]:
    creds = get_secret_json(app_secret_arn)
    return {
        "client_id": creds.get("client_id", ""),
        "client_secret": creds.get("client_secret", ""),
        "refresh_token": creds.get("refresh_token", ""),
    }
