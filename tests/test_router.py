"""
Unit tests for event router functionality
"""
import json
from unittest.mock import MagicMock, patch

from src.app.router import handle_event


HEADERS_FORM = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Slack-Request-Timestamp": "1234567890",
    "X-Slack-Signature": "v0=test-signature",
}


def _payload_form(data: dict) -> str:
    return "payload=" + json.dumps(data)


class TestEventRouter:
    """Test cases for event routing functionality"""

    def test_ses_event_routing(self) -> None:
        ses_event = {
            "Records": [
                {
                    "ses": {
                        "mail": {
                            "source": "test@example.com",
                            "commonHeaders": {"subject": "Test Subject"},
                            "messageId": "test-message-id",
                        }
                    },
                    "body": "Test email body",
                }
            ]
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch("src.app.router.redact_and_map") as mock_redact,
            patch("src.app.router.put_context_item") as mock_put,
            patch(
                "src.app.router.resolve_slack_credentials"
            ) as mock_creds,
            patch("src.app.router.SlackClient") as mock_slack,
        ):
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_channel_id="C1234567890",
            )
            mock_redact.return_value = ("Test email body", {})
            mock_creds.return_value = {"bot_token": "xoxb-test-token"}
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            response = handle_event(ses_event)

            assert response["statusCode"] == 200
            assert "ses event accepted" in response["body"]
            mock_put.assert_called_once()
            mock_slack_instance.post_message.assert_called_once()

    def test_slack_block_actions_routing(self) -> None:
        payload = {
            "type": "block_actions",
            "trigger_id": "test-trigger-id",
            "actions": [{"value": json.dumps({"context_id": "test-context"})}],
        }
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": HEADERS_FORM,
            "body": _payload_form(payload),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch(
                "src.app.router.resolve_slack_credentials"
            ) as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
            patch("src.app.router.generate_reply_draft") as mock_generate,
            patch("src.app.router.reidentify") as mock_reidentify,
            patch("src.app.router.SlackClient") as mock_slack,
        ):
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
            )
            mock_verify.return_value = True
            mock_creds.return_value = {"bot_token": "xoxb-test-token"}
            mock_get.return_value = {"body_redacted": "red", "pii_map": "{}"}
            mock_generate.return_value = "Generated reply"
            mock_reidentify.return_value = "Generated reply"
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            response = handle_event(event)

            assert response["statusCode"] == 200
            assert response["body"] == '{"ack": true}'
            mock_slack_instance.open_modal.assert_called_once()

    def test_slack_view_submission_routing(self) -> None:
        view = {
            "private_metadata": json.dumps({"context_id": "ctx-id"}),
            "state": {
                "values": {
                    "editable_reply_block": {
                        "editable_reply_input": {"value": "Edited"}
                    }
                }
            },
        }
        payload = {"type": "view_submission", "view": view}
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": HEADERS_FORM,
            "body": _payload_form(payload),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch(
                "src.app.router.resolve_slack_credentials"
            ) as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
            patch("src.app.router.get_context_item") as mock_get,
            patch("src.app.router.send_email") as mock_send,
            patch("src.app.router.SlackClient") as mock_slack,
        ):
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                sender_email_address="support@example.com",
                slack_channel_id="C1234567890",
            )
            mock_verify.return_value = True
            mock_creds.return_value = {"bot_token": "xoxb-test-token"}
            mock_get.return_value = {
                "sender_email": "customer@example.com",
                "subject": "Re: Test Subject",
            }
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance

            response = handle_event(event)

            assert response["statusCode"] == 200
            assert response["body"] == '{"response_action": "clear"}'
            mock_send.assert_called_once_with(
                sender="support@example.com",
                to_addresses=["customer@example.com"],
                subject="Re: Test Subject",
                body="Edited",
            )
            mock_slack_instance.post_message.assert_called_once()

    def test_unknown_event_type(self) -> None:
        with patch("src.app.router.load_config") as mock_config:
            mock_config.return_value = MagicMock()
            response = handle_event({"unknown": "event"})
            assert response["statusCode"] == 400
            assert "unrecognized event" in response["body"]

    def test_slack_signature_verification_failure(self) -> None:
        payload = {"type": "block_actions"}
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": HEADERS_FORM,
            "body": _payload_form(payload),
        }

        with (
            patch("src.app.router.load_config") as mock_config,
            patch(
                "src.app.router.resolve_slack_credentials"
            ) as mock_creds,
            patch("src.app.router.verify_slack_signature") as mock_verify,
        ):
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
                slack_app_secret_arn=(
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
                ),
            )
            mock_creds.return_value = {"signing_secret": "test-secret"}
            mock_verify.return_value = False

            response = handle_event(event)

            assert response["statusCode"] == 401
            assert "unauthorized" in response["body"]
