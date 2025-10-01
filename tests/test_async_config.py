"""
Unit tests for async endpoint configuration
"""
import os
import pytest
from unittest.mock import patch

from src.app.common.config import AppConfig, load_config


class TestAsyncConfig:
    """Test async endpoint configuration functionality"""

    def test_app_config_with_async_endpoint(self):
        """Test AppConfig includes async endpoint fields"""
        config = AppConfig(
            stage="staging",
            slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            openai_api_key_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:openai",
            slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:slack",
            ddb_table_name="test-table",
            sender_email_address="test@example.com",
            slack_channel_id="C1234567890",
            gmail_oauth_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:gmail",
            ses_inbound_bucket_name="test-bucket",
            ses_inbound_prefix="inbound/",
            async_generation_endpoint="https://test-cloudrun.example.com/async/generate",
            async_generation_auth_header="Bearer test-token"
        )

        assert config.async_generation_endpoint == "https://test-cloudrun.example.com/async/generate"
        assert config.async_generation_auth_header == "Bearer test-token"

    def test_load_config_with_async_env_vars(self):
        """Test load_config reads async environment variables"""
        env_vars = {
            "STAGE": "staging",
            "SLACK_SIGNING_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            "OPENAI_API_KEY_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:openai",
            "SLACK_APP_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:slack",
            "DDB_TABLE_NAME": "test-table",
            "SENDER_EMAIL_ADDRESS": "test@example.com",
            "SLACK_CHANNEL_ID": "C1234567890",
            "GMAIL_OAUTH_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:gmail",
            "SES_INBOUND_BUCKET_NAME": "test-bucket",
            "SES_INBOUND_PREFIX": "inbound/",
            "ASYNC_GENERATION_ENDPOINT": "https://test-cloudrun.example.com/async/generate",
            "ASYNC_GENERATION_AUTH_HEADER": "Bearer test-token"
        }

        with patch.dict(os.environ, env_vars):
            config = load_config()

            assert config.async_generation_endpoint == "https://test-cloudrun.example.com/async/generate"
            assert config.async_generation_auth_header == "Bearer test-token"

    def test_load_config_without_async_env_vars(self):
        """Test load_config with empty async environment variables"""
        env_vars = {
            "STAGE": "staging",
            "SLACK_SIGNING_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            "OPENAI_API_KEY_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:openai",
            "SLACK_APP_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:slack",
            "DDB_TABLE_NAME": "test-table",
            "SENDER_EMAIL_ADDRESS": "test@example.com",
            "SLACK_CHANNEL_ID": "C1234567890",
            "GMAIL_OAUTH_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:gmail",
            "SES_INBOUND_BUCKET_NAME": "test-bucket",
            "SES_INBOUND_PREFIX": "inbound/",
            "ASYNC_GENERATION_ENDPOINT": "",
            "ASYNC_GENERATION_AUTH_HEADER": ""
        }

        with patch.dict(os.environ, env_vars):
            config = load_config()

            assert config.async_generation_endpoint == ""
            assert config.async_generation_auth_header == ""

    def test_load_config_missing_async_env_vars(self):
        """Test load_config with missing async environment variables"""
        env_vars = {
            "STAGE": "staging",
            "SLACK_SIGNING_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            "OPENAI_API_KEY_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:openai",
            "SLACK_APP_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:slack",
            "DDB_TABLE_NAME": "test-table",
            "SENDER_EMAIL_ADDRESS": "test@example.com",
            "SLACK_CHANNEL_ID": "C1234567890",
            "GMAIL_OAUTH_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:gmail",
            "SES_INBOUND_BUCKET_NAME": "test-bucket",
            "SES_INBOUND_PREFIX": "inbound/"
            # Missing ASYNC_GENERATION_* variables
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()

            assert config.async_generation_endpoint == ""
            assert config.async_generation_auth_header == ""

    def test_async_endpoint_validation(self):
        """Test async endpoint URL validation scenarios"""
        # Valid HTTPS endpoint
        config = AppConfig(
            stage="staging",
            slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            openai_api_key_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:openai",
            slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:slack",
            ddb_table_name="test-table",
            sender_email_address="test@example.com",
            slack_channel_id="C1234567890",
            gmail_oauth_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:gmail",
            ses_inbound_bucket_name="test-bucket",
            ses_inbound_prefix="inbound/",
            async_generation_endpoint="https://test-cloudrun.example.com/async/generate",
            async_generation_auth_header="Bearer test-token"
        )

        assert config.async_generation_endpoint.startswith("https://")
        assert "/async/generate" in config.async_generation_endpoint

    def test_auth_header_formats(self):
        """Test different auth header formats"""
        test_cases = [
            "Bearer test-token",
            "Basic dGVzdDp0ZXN0",  # base64 encoded
            "CustomAuth custom-token",
            "ApiKey api-key-value"
        ]

        for auth_header in test_cases:
            config = AppConfig(
                stage="staging",
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                openai_api_key_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:openai",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:slack",
                ddb_table_name="test-table",
                sender_email_address="test@example.com",
                slack_channel_id="C1234567890",
                gmail_oauth_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:gmail",
                ses_inbound_bucket_name="test-bucket",
                ses_inbound_prefix="inbound/",
                async_generation_endpoint="https://test-cloudrun.example.com/async/generate",
                async_generation_auth_header=auth_header
            )

            assert config.async_generation_auth_header == auth_header

    def test_config_immutability(self):
        """Test that AppConfig is immutable (frozen dataclass)"""
        config = AppConfig(
            stage="staging",
            slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            openai_api_key_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:openai",
            slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:slack",
            ddb_table_name="test-table",
            sender_email_address="test@example.com",
            slack_channel_id="C1234567890",
            gmail_oauth_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:gmail",
            ses_inbound_bucket_name="test-bucket",
            ses_inbound_prefix="inbound/",
            async_generation_endpoint="https://test-cloudrun.example.com/async/generate",
            async_generation_auth_header="Bearer test-token"
        )

        # Attempting to modify should raise an exception
        with pytest.raises(AttributeError):
            config.async_generation_endpoint = "https://new-endpoint.com"

        with pytest.raises(AttributeError):
            config.async_generation_auth_header = "New token"
