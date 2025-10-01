"""
E2E tests for async Slack workflow with Cloud Run integration
"""
import json
from unittest.mock import patch, MagicMock

from src.app.router import handle_event


class TestAsyncSlackWorkflow:
    """Test async Slack workflow end-to-end scenarios"""

    def test_async_generation_workflow_with_endpoint(self):
        """Test complete async workflow when ASYNC_GENERATION_ENDPOINT is
        configured"""
        # Mock configuration with async endpoint
        mock_config = MagicMock()
        mock_config.async_generation_endpoint = (
            "https://test-cloudrun.example.com/async/generate"
        )
        mock_config.async_generation_auth_header = "Bearer test-token"
        mock_config.stage = "staging"
        mock_config.slack_signing_secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        )
        mock_config.slack_app_secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        )
        mock_config.slack_channel_id = "C1234567890"

        # Mock Slack credentials
        mock_creds = {
            "bot_token": "xoxb-test-token",
            "signing_secret": "test-signing-secret",
        }

        # Mock DynamoDB context
        mock_context = {
            "context_id": "test-context-123",
            "body_redacted": "Test email content with [PERSON_1]",
            "pii_map": '{"[PERSON_1]": "John Doe"}',
        }

        # Create Slack block_actions event
        slack_event = {
            "requestContext": {
                "http": {
                    "method": "POST"
                }
            },
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=test-signature"
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test-trigger-id",
                "actions": [{
                    "action_id": "generate_reply_action",
                    "value": json.dumps({"context_id": "test-context-123"})
                }]
            }),
            "isBase64Encoded": False
        }

        with (
            patch("src.app.router.load_config", return_value=mock_config),
            patch(
                "src.app.router.resolve_slack_credentials",
                return_value=mock_creds
            ),
            patch(
                "src.app.router.verify_slack_signature", return_value=True
            ),
            patch(
                "src.app.router.get_context_item", return_value=mock_context
            ),
            patch("src.app.router.SlackClient") as mock_slack_client,
            patch("urllib.request.urlopen") as mock_urlopen
        ):
            # Mock Slack client
            mock_slack_instance = MagicMock()
            mock_slack_client.return_value = mock_slack_instance

            # Mock async endpoint call
            mock_response = MagicMock()
            mock_response.status = 200
            mock_urlopen.return_value = mock_response

            # Execute the event handler
            response = handle_event(slack_event)

            # Verify response
            assert response["statusCode"] == 200
            response_body = json.loads(response["body"])
            assert response_body["ack"] is True

            # Verify modal was opened immediately
            mock_slack_instance.open_modal.assert_called_once()
            call_args = mock_slack_instance.open_modal.call_args
            assert call_args[1]["trigger_id"] == "test-trigger-id"

            # Verify modal has external_id for async updates
            view = call_args[1]["view"]
            assert view["external_id"] == "ai-reply-test-context-123"

            # Verify async endpoint was called
            mock_urlopen.assert_called_once()
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert request.get_full_url() == (
                "https://test-cloudrun.example.com/async/generate"
            )
            assert request.get_method() == "POST"

            # Verify request payload
            payload = json.loads(request.data.decode('utf-8'))
            assert payload["context_id"] == "test-context-123"
            assert payload["external_id"] == "ai-reply-test-context-123"
            assert payload["stage"] == "staging"

            # Verify authorization header
            assert request.get_header("Authorization") == "Bearer test-token"

    def test_sync_generation_workflow_without_endpoint(self):
        """Test sync workflow when ASYNC_GENERATION_ENDPOINT is not
        configured"""
        # Mock configuration without async endpoint
        mock_config = MagicMock()
        mock_config.async_generation_endpoint = ""
        mock_config.async_generation_auth_header = ""
        mock_config.stage = "staging"
        mock_config.slack_signing_secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        )
        mock_config.slack_app_secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        )
        mock_config.slack_channel_id = "C1234567890"

        # Mock Slack credentials
        mock_creds = {
            "bot_token": "xoxb-test-token",
            "signing_secret": "test-signing-secret",
        }

        # Mock DynamoDB context
        mock_context = {
            "context_id": "test-context-123",
            "body_redacted": "Test email content with [PERSON_1]",
            "pii_map": '{"[PERSON_1]": "John Doe"}',
        }

        # Create Slack block_actions event
        slack_event = {
            "requestContext": {
                "http": {
                    "method": "POST"
                }
            },
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=test-signature"
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test-trigger-id",
                "actions": [{
                    "action_id": "generate_reply_action",
                    "value": json.dumps({"context_id": "test-context-123"})
                }]
            }),
            "isBase64Encoded": False
        }

        with (
            patch("src.app.router.load_config", return_value=mock_config),
            patch(
                "src.app.router.resolve_slack_credentials",
                return_value=mock_creds
            ),
            patch(
                "src.app.router.verify_slack_signature", return_value=True
            ),
            patch(
                "src.app.router.get_context_item", return_value=mock_context
            ),
            patch(
                "src.app.router.generate_reply_draft",
                return_value="Generated reply text"
            ),
            patch(
                "src.app.router.reidentify",
                return_value="Hello John Doe, thank you for your message."
            ),
            patch("src.app.router.SlackClient") as mock_slack_client,
            patch("urllib.request.urlopen") as mock_urlopen
        ):
            # Mock Slack client
            mock_slack_instance = MagicMock()
            mock_slack_client.return_value = mock_slack_instance

            # Execute the event handler
            response = handle_event(slack_event)

            # Verify response
            assert response["statusCode"] == 200
            response_body = json.loads(response["body"])
            assert response_body["ack"] is True

            # Verify modal was opened with generated content
            mock_slack_instance.open_modal.assert_called_once()
            call_args = mock_slack_instance.open_modal.call_args
            view = call_args[1]["view"]

            # Verify initial text contains generated content
            initial_text = view["blocks"][1]["element"]["initial_value"]
            assert (
                "Hello John Doe, thank you for your message." in initial_text
            )

            # Verify async endpoint was NOT called
            mock_urlopen.assert_not_called()

    def test_async_endpoint_failure_handling(self):
        """Test handling when async endpoint call fails"""
        # Mock configuration with async endpoint
        mock_config = MagicMock()
        mock_config.async_generation_endpoint = (
            "https://test-cloudrun.example.com/async/generate"
        )
        mock_config.async_generation_auth_header = "Bearer test-token"
        mock_config.stage = "staging"
        mock_config.slack_signing_secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        )
        mock_config.slack_app_secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        )
        mock_config.slack_channel_id = "C1234567890"

        # Mock Slack credentials
        mock_creds = {
            "bot_token": "xoxb-test-token",
            "signing_secret": "test-signing-secret",
        }

        # Mock DynamoDB context
        mock_context = {
            "context_id": "test-context-123",
            "body_redacted": "Test email content",
            "pii_map": '{}',
        }

        # Create Slack block_actions event
        slack_event = {
            "requestContext": {
                "http": {
                    "method": "POST"
                }
            },
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=test-signature"
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test-trigger-id",
                "actions": [{
                    "action_id": "generate_reply_action",
                    "value": json.dumps({"context_id": "test-context-123"})
                }]
            }),
            "isBase64Encoded": False
        }

        with (
            patch("src.app.router.load_config", return_value=mock_config),
            patch(
                "src.app.router.resolve_slack_credentials",
                return_value=mock_creds
            ),
            patch(
                "src.app.router.verify_slack_signature", return_value=True
            ),
            patch(
                "src.app.router.get_context_item", return_value=mock_context
            ),
            patch("src.app.router.SlackClient") as mock_slack_client,
            patch(
                "urllib.request.urlopen",
                side_effect=Exception("Network error")
            )
        ):
            # Mock Slack client
            mock_slack_instance = MagicMock()
            mock_slack_client.return_value = mock_slack_instance

            # Execute the event handler
            response = handle_event(slack_event)

            # Verify response still succeeds (modal opened)
            assert response["statusCode"] == 200
            response_body = json.loads(response["body"])
            assert response_body["ack"] is True

            # Verify modal was still opened
            mock_slack_instance.open_modal.assert_called_once()

            # Note: Error handling is done silently in the current
            # implementation. The async endpoint failure doesn't prevent
            # modal opening

    def test_modal_external_id_generation(self):
        """Test that external_id is properly generated for modal updates"""
        mock_config = MagicMock()
        mock_config.async_generation_endpoint = (
            "https://test-cloudrun.example.com/async/generate"
        )
        mock_config.async_generation_auth_header = "Bearer test-token"
        mock_config.stage = "staging"
        mock_config.slack_signing_secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        )
        mock_config.slack_app_secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        )
        mock_config.slack_channel_id = "C1234567890"

        mock_creds = {
            "bot_token": "xoxb-test-token",
            "signing_secret": "test-signing-secret",
        }

        mock_context = {
            "context_id": "unique-context-456",
            "body_redacted": "Test content",
            "pii_map": '{}',
        }

        slack_event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=test-signature"
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions",
                "trigger_id": "test-trigger-id",
                "actions": [{
                    "action_id": "generate_reply_action",
                    "value": json.dumps({"context_id": "unique-context-456"})
                }]
            }),
            "isBase64Encoded": False
        }

        with (
            patch("src.app.router.load_config", return_value=mock_config),
            patch(
                "src.app.router.resolve_slack_credentials",
                return_value=mock_creds
            ),
            patch(
                "src.app.router.verify_slack_signature", return_value=True
            ),
            patch(
                "src.app.router.get_context_item", return_value=mock_context
            ),
            patch("src.app.router.SlackClient") as mock_slack_client,
            patch("urllib.request.urlopen") as mock_urlopen
        ):
            mock_slack_instance = MagicMock()
            mock_slack_client.return_value = mock_slack_instance

            handle_event(slack_event)

            # Verify external_id format
            call_args = mock_slack_instance.open_modal.call_args
            view = call_args[1]["view"]
            assert view["external_id"] == "ai-reply-unique-context-456"

            # Verify async payload includes same external_id
            request = mock_urlopen.call_args[0][0]
            payload = json.loads(request.data.decode('utf-8'))
            assert payload["external_id"] == "ai-reply-unique-context-456"
