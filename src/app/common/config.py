import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    stage: str
    slack_signing_secret_arn: str
    openai_api_key_secret_arn: str
    slack_app_secret_arn: str
    ddb_table_name: str
    sender_email_address: str
    slack_channel_id: str
    gmail_oauth_secret_arn: str
    ses_inbound_bucket_name: str
    ses_inbound_prefix: str


def load_config() -> AppConfig:
    return AppConfig(
        stage=os.getenv("STAGE", "dev"),
        slack_signing_secret_arn=os.getenv("SLACK_SIGNING_SECRET_ARN", ""),
        openai_api_key_secret_arn=os.getenv("OPENAI_API_KEY_SECRET_ARN", ""),
        slack_app_secret_arn=os.getenv("SLACK_APP_SECRET_ARN", ""),
        ddb_table_name=os.getenv("DDB_TABLE_NAME", ""),
        sender_email_address=os.getenv("SENDER_EMAIL_ADDRESS", ""),
        slack_channel_id=os.getenv("SLACK_CHANNEL_ID", ""),
        gmail_oauth_secret_arn=os.getenv("GMAIL_OAUTH_SECRET_ARN", ""),
        ses_inbound_bucket_name=os.getenv("SES_INBOUND_BUCKET_NAME", ""),
        ses_inbound_prefix=os.getenv("SES_INBOUND_PREFIX", ""),
    )
