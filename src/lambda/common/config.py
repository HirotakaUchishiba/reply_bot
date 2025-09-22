import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    stage: str
    slack_signing_secret_arn: str
    openai_api_key_secret_arn: str
    slack_app_secret_arn: str
    ddb_table_name: str


def load_config() -> AppConfig:
    return AppConfig(
        stage=os.getenv("STAGE", "dev"),
        slack_signing_secret_arn=os.getenv("SLACK_SIGNING_SECRET_ARN", ""),
        openai_api_key_secret_arn=os.getenv("OPENAI_API_KEY_SECRET_ARN", ""),
        slack_app_secret_arn=os.getenv("SLACK_APP_SECRET_ARN", ""),
        ddb_table_name=os.getenv("DDB_TABLE_NAME", ""),
    )