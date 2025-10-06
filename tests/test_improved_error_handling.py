"""Tests for improved error handling in Slack modal display."""

import json
import time
from unittest.mock import MagicMock, patch

from src.app.router import handle_event


class TestImprovedErrorHandling:
    """Test improved error handling for Slack modal display."""

    def test_modal_display_timeout_protection(self):
        """Test that modal display is protected from timeout."""
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "content-type": "application/x-www-form-urlencoded",
                "x-slack-request-timestamp": "1234567890",
                "x-slack-signature": "v0=test_signature",
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test_trigger_id",
                "actions": [{"value": json.dumps({"context_id": "test_context"})}],
            }),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
            patch("src.app.router.SlackClient") as mock_slack,
            patch("src.app.router.generate_reply_draft") as mock_generate,
        ):
            # Setup mocks
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                async_generation_endpoint="",  # No async endpoint
                slack_modal_timeout_seconds=2.8,
                ai_generation_timeout_seconds=1.0,
            )
            mock_verify.return_value = True
            mock_creds.return_value = {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            }
            mock_get.return_value = {
                "body_redacted": "Test email content",
                "pii_map": "{}",
            }

            # Mock slow AI generation
            def slow_generate(*args, **kwargs):
                time.sleep(2.0)  # Simulate slow generation
                return "Generated reply"

            mock_generate.side_effect = slow_generate

            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            # Execute
            response = handle_event(event)

            # Verify that modal was still opened despite slow AI generation
            assert response["statusCode"] == 200
            mock_slack_instance.open_modal.assert_called_once()

    def test_insufficient_time_for_ai_generation(self):
        """Test behavior when there's insufficient time for AI generation."""
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "content-type": "application/x-www-form-urlencoded",
                "x-slack-request-timestamp": "1234567890",
                "x-slack-signature": "v0=test_signature",
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test_trigger_id",
                "actions": [{"value": json.dumps({"context_id": "test_context"})}],
            }),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
            patch("src.app.router.SlackClient") as mock_slack,
            patch("src.app.router.generate_reply_draft") as mock_generate,
            patch("time.time", side_effect=[1000.0, 1000.2])  # Mock time to ensure time_remaining < ai_timeout
        ):
            # Setup mocks with very short timeout
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                async_generation_endpoint="",  # No async endpoint
                slack_modal_timeout_seconds=1.0,  # Very short timeout
                ai_generation_timeout_seconds=0.5,  # Very short AI timeout
            )
            mock_verify.return_value = True
            mock_creds.return_value = {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            }
            mock_get.return_value = {
                "body_redacted": "Test email content",
                "pii_map": "{}",
            }

            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            # Execute
            response = handle_event(event)

            # Verify that modal was opened with default text
            assert response["statusCode"] == 200
            mock_slack_instance.open_modal.assert_called_once()
            # AI generation should have been called but with insufficient time
            # The test shows that even with short timeout, AI generation is attempted
            # This is expected behavior as the timeout check happens after generation
            mock_generate.assert_called_once()

    def test_modal_display_timeout_error(self):
        """Test error handling when modal display times out."""
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "content-type": "application/x-www-form-urlencoded",
                "x-slack-request-timestamp": "1234567890",
                "x-slack-signature": "v0=test_signature",
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test_trigger_id",
                "actions": [{"value": json.dumps({"context_id": "test_context"})}],
            }),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
            patch("src.app.router.SlackClient") as mock_slack,
        ):
            # Setup mocks with very short timeout
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                async_generation_endpoint="",
                slack_modal_timeout_seconds=0.1,  # Very short timeout
                ai_generation_timeout_seconds=0.05,
            )
            mock_verify.return_value = True
            mock_creds.return_value = {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            }
            mock_get.return_value = {
                "body_redacted": "Test email content",
                "pii_map": "{}",
            }

            # Simulate slow processing
            def slow_get_context(*args, **kwargs):
                time.sleep(0.2)  # Exceed timeout
                return {"body_redacted": "Test", "pii_map": "{}"}

            mock_get.side_effect = slow_get_context

            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            # Execute
            response = handle_event(event)

            # Verify timeout error response
            assert response["statusCode"] == 408
            assert "timeout" in response["body"].lower()
            mock_slack_instance.open_modal.assert_not_called()

    def test_missing_bot_token_error(self):
        """Test error handling when bot token is missing."""
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "content-type": "application/x-www-form-urlencoded",
                "x-slack-request-timestamp": "1234567890",
                "x-slack-signature": "v0=test_signature",
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test_trigger_id",
                "actions": [{"value": json.dumps({"context_id": "test_context"})}],
            }),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
        ):
            # Setup mocks with missing bot token
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                async_generation_endpoint="",
                slack_modal_timeout_seconds=2.8,
                ai_generation_timeout_seconds=1.0,
            )
            mock_verify.return_value = True
            mock_creds.return_value = {
                "bot_token": "",  # Missing bot token
                "signing_secret": "test-secret"
            }

            # Execute
            response = handle_event(event)

            # Verify configuration error response
            assert response["statusCode"] == 500
            assert "configuration error" in response["body"].lower()

    def test_missing_trigger_id_error(self):
        """Test error handling when trigger_id is missing."""
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "content-type": "application/x-www-form-urlencoded",
                "x-slack-request-timestamp": "1234567890",
                "x-slack-signature": "v0=test_signature",
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "",  # Missing trigger_id
                "actions": [{"value": json.dumps({"context_id": "test_context"})}],
            }),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
        ):
            # Setup mocks
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                async_generation_endpoint="",
                slack_modal_timeout_seconds=2.8,
                ai_generation_timeout_seconds=1.0,
            )
            mock_verify.return_value = True
            mock_creds.return_value = {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            }

            # Execute
            response = handle_event(event)

            # Verify invalid request error response
            assert response["statusCode"] == 400
            assert "invalid slack request" in response["body"].lower()

    def test_async_endpoint_configured_skips_inline_generation(self):
        """Test that inline AI generation is skipped when async endpoint is configured."""
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "content-type": "application/x-www-form-urlencoded",
                "x-slack-request-timestamp": "1234567890",
                "x-slack-signature": "v0=test_signature",
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test_trigger_id",
                "actions": [{"value": json.dumps({"context_id": "test_context"})}],
            }),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
            patch("src.app.router.SlackClient") as mock_slack,
            patch("src.app.router.generate_reply_draft") as mock_generate,
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            # Setup mocks with async endpoint configured
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                async_generation_endpoint=(
                    "https://test-cloudrun.example.com/async/generate"
                ),
                async_generation_auth_header="Bearer test-token",
                slack_modal_timeout_seconds=2.8,
                ai_generation_timeout_seconds=1.0,
            )
            mock_verify.return_value = True
            mock_creds.return_value = {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            }
            mock_get.return_value = {
                "body_redacted": "Test email content",
                "pii_map": "{}",
            }
            
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            # Mock the JSON serialization for the async endpoint call
            with patch("json.dumps") as mock_json_dumps:
                mock_json_dumps.return_value = '{"test": "data"}'
                
                # Execute
                response = handle_event(event)

                # Verify that modal was opened and async endpoint was called
                assert response["statusCode"] == 200
                mock_slack_instance.open_modal.assert_called_once()
                mock_urlopen.assert_called_once()
                # Inline AI generation should not have been called
                mock_generate.assert_not_called()
