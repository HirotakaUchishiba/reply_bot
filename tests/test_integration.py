"""
Integration tests for the Slack AI Email Assistant
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from src.app.router import handle_event


class TestIntegration:
    """Integration tests for the complete workflow"""

    def test_complete_email_workflow(self):
        """Test the complete workflow from email receipt to reply generation"""
        # Mock SES event
        ses_event = {
            "Records": [
                {
                    "ses": {
                        "mail": {
                            "source": "customer@example.com",
                            "commonHeaders": {"subject": "Test Inquiry"},
                            "messageId": "test-message-123",
                        }
                    },
                    "body": "Hello, I have a question about your service.",
                }
            ]
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.redact_and_map") as mock_redact,
            patch("src.app.router.put_context_item") as mock_put,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.SlackClient") as mock_slack,
        ):
            # Setup mocks
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_channel_id="C1234567890",
            )
            mock_redact.return_value = ("Hello, I have a question about your service.", {})
            mock_creds.return_value = {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            }
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            # Execute SES event handling
            response = handle_event(ses_event)

            # Verify response
            assert response["statusCode"] == 200
            assert "ses event accepted" in response["body"]

            # Verify context was saved
            mock_put.assert_called_once()
            saved_item = mock_put.call_args[0][0]
            assert saved_item["context_id"] == "test-message-123"
            assert saved_item["sender_email"] == "customer@example.com"
            assert saved_item["subject"] == "Test Inquiry"

            # Verify Slack notification was sent
            mock_slack_instance.post_message.assert_called_once()

    def test_slack_block_actions_workflow(self):
        """Test Slack block actions workflow"""
        payload = {
            "type": "block_actions",
            "trigger_id": "test-trigger-id",
            "actions": [{"value": json.dumps({"context_id": "test-context-123"})}],
        }
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=test-signature",
            },
            "body": "payload=" + json.dumps(payload),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
            patch("src.app.router.generate_reply_draft") as mock_generate,
            patch("src.app.router.reidentify") as mock_reidentify,
            patch("src.app.router.SlackClient") as mock_slack,
        ):
            # Setup mocks
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            )
            mock_verify.return_value = True
            mock_creds.return_value = {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            }
            mock_get.return_value = {
                "body_redacted": "Hello, I have a question about your service.",
                "pii_map": "{}"
            }
            mock_generate.return_value = "Thank you for your inquiry. We will get back to you soon."
            mock_reidentify.return_value = "Thank you for your inquiry. We will get back to you soon."
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            # Execute block actions handling
            response = handle_event(event)

            # Verify response
            assert response["statusCode"] == 200
            assert response["body"] == '{"ack": true}'

            # Verify modal was opened
            mock_slack_instance.open_modal.assert_called_once()

    def test_slack_view_submission_workflow(self):
        """Test Slack view submission workflow"""
        view = {
            "private_metadata": json.dumps({"context_id": "test-context-123"}),
            "state": {
                "values": {
                    "editable_reply_block": {
                        "editable_reply_input": {"value": "Thank you for your inquiry. We will get back to you soon."}
                    }
                }
            },
        }
        payload = {"type": "view_submission", "view": view}
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=test-signature",
            },
            "body": "payload=" + json.dumps(payload),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
            patch("src.app.router.send_email") as mock_send,
            patch("src.app.router.SlackClient") as mock_slack,
        ):
            # Setup mocks
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                sender_email_address="support@example.com",
                slack_channel_id="C1234567890",
            )
            mock_verify.return_value = True
            mock_creds.return_value = {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            }
            mock_get.return_value = {
                "sender_email": "customer@example.com",
                "subject": "Re: Test Inquiry",
            }
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            # Execute view submission handling
            response = handle_event(event)

            # Verify response
            assert response["statusCode"] == 200
            assert response["body"] == '{"response_action": "clear"}'

            # Verify email was sent
            mock_send.assert_called_once_with(
                sender="support@example.com",
                to_addresses=["customer@example.com"],
                subject="Re: Test Inquiry",
                body="Thank you for your inquiry. We will get back to you soon.",
            )

            # Verify confirmation message was sent
            mock_slack_instance.post_message.assert_called_once()

    def test_error_handling_missing_context(self):
        """Test error handling when context is missing"""
        view = {
            "private_metadata": json.dumps({"context_id": "missing-context"}),
            "state": {
                "values": {
                    "editable_reply_block": {
                        "editable_reply_input": {"value": "Test reply"}
                    }
                }
            },
        }
        payload = {"type": "view_submission", "view": view}
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=test-signature",
            },
            "body": "payload=" + json.dumps(payload),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
        ):
            # Setup mocks
            mock_config.return_value = MagicMock()
            mock_verify.return_value = True
            mock_creds.return_value = {"signing_secret": "test-secret"}
            mock_get.return_value = None  # Context not found

            # Execute view submission handling
            response = handle_event(event)

            # Verify error response
            assert response["statusCode"] == 200
            assert response["body"] == '{"response_action": "clear"}'

    def test_slack_signature_verification_failure(self):
        """Test handling of invalid Slack signature"""
        payload = {"type": "block_actions"}
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=invalid-signature",
            },
            "body": "payload=" + json.dumps(payload),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.resolve_slack_credentials") as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
        ):
            # Setup mocks
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            )
            mock_creds.return_value = {"signing_secret": "test-secret"}
            mock_verify.return_value = False  # Invalid signature

            # Execute request handling
            response = handle_event(event)

            # Verify unauthorized response
            assert response["statusCode"] == 401
            assert "unauthorized" in response["body"]
