"""Configuration management for Cloud Run Job worker."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class JobWorkerConfig:
    """Configuration for Cloud Run Job worker."""
    
    # Required environment variables
    openai_api_key: str
    slack_bot_token: str
    ddb_table_name: str
    
    # Optional environment variables
    aws_region: str = "ap-northeast-1"
    openai_timeout: int = 30
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "JobWorkerConfig":
        """Create configuration from environment variables."""
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN", "")
        ddb_table_name = os.getenv("DDB_TABLE_NAME", "")
        
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not slack_bot_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")
        if not ddb_table_name:
            raise ValueError("DDB_TABLE_NAME environment variable is required")
        
        return cls(
            openai_api_key=openai_api_key,
            slack_bot_token=slack_bot_token,
            ddb_table_name=ddb_table_name,
            aws_region=os.getenv("AWS_REGION", "ap-northeast-1"),
            openai_timeout=int(os.getenv("OPENAI_TIMEOUT", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
