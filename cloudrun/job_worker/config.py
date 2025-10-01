"""Configuration management for Cloud Run Job worker."""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobWorkerConfig:
    """Configuration for Cloud Run Job worker."""
    
    # Required environment variables
    openai_api_key: str
    slack_bot_token: str
    ddb_table_name: str
    
    # AWS Workload Identity configuration
    aws_region: str = "ap-northeast-1"
    aws_role_arn: str = ""
    gcp_service_account_email: str = ""
    workload_identity_provider: str = ""
    
    # Optional environment variables
    openai_timeout: int = 30
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "JobWorkerConfig":
        """Create configuration from environment variables."""
        # Get secret names from environment
        openai_secret_name = os.getenv("OPENAI_API_KEY_SECRET_NAME", "")
        slack_secret_name = os.getenv("SLACK_BOT_TOKEN_SECRET_NAME", "")
        ddb_table_name = os.getenv("DDB_TABLE_NAME", "")
        
        if not openai_secret_name:
            raise ValueError("OPENAI_API_KEY_SECRET_NAME environment variable is required")
        if not slack_secret_name:
            raise ValueError("SLACK_BOT_TOKEN_SECRET_NAME environment variable is required")
        if not ddb_table_name:
            raise ValueError("DDB_TABLE_NAME environment variable is required")
        
        # Retrieve secrets from GCP Secret Manager
        openai_api_key = cls._get_gcp_secret(openai_secret_name)
        slack_bot_token = cls._get_gcp_secret(slack_secret_name)
        
        if not openai_api_key:
            raise ValueError("Failed to retrieve OpenAI API key from Secret Manager")
        if not slack_bot_token:
            raise ValueError("Failed to retrieve Slack bot token from Secret Manager")
        
        return cls(
            openai_api_key=openai_api_key,
            slack_bot_token=slack_bot_token,
            ddb_table_name=ddb_table_name,
            aws_region=os.getenv("AWS_REGION", "ap-northeast-1"),
            aws_role_arn=os.getenv("AWS_ROLE_ARN", ""),
            gcp_service_account_email=os.getenv("GCP_SERVICE_ACCOUNT_EMAIL", ""),
            workload_identity_provider=os.getenv("WORKLOAD_IDENTITY_PROVIDER", ""),
            openai_timeout=int(os.getenv("OPENAI_TIMEOUT", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
    
    @staticmethod
    def _get_gcp_secret(secret_name: str) -> str:
        """Get secret value from Google Cloud Secret Manager."""
        try:
            from google.cloud import secretmanager
            
            project_id = os.getenv("GCP_PROJECT_ID")
            if not project_id:
                raise ValueError("GCP_PROJECT_ID environment variable is required")
            
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
            
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            return ""
