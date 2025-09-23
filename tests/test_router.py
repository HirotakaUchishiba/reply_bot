"""
Unit tests for event router functionality
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from src.lambda.router import handle_event


class TestEventRouter:
    """Test cases for event routing functionality"""
    
    def test_ses_event_routing(self):
        """Test that SES events are properly routed"""
        ses_event = {
            "Records": [
                {
                    "ses": {
                        "mail": {
                            "source": "test@example.com",
                            "commonHeaders": {
                                "subject": "Test Subject"
                            },
                            "messageId": "test-message-id"
                        }
                    },
                    "body": "Test email body"
                }
            ]
        }
        
        with patch('src.lambda.router.load_config') as mock_config, \
             patch('src.lambda.router.redact_and_map') as mock_redact, \
             patch('src.lambda.router.put_context_item') as mock_put, \
             patch('src.lambda.router.resolve_slack_credentials') as mock_creds, \
             patch('src.lambda.router.SlackClient') as mock_slack:
            
            # Mock configuration
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_channel_id="C1234567890"
            )
            
            # Mock PII redaction
            mock_redact.return_value = ("Test email body", {})
            
            # Mock Slack credentials
            mock_creds.return_value = {"bot_token": "xoxb-test-token"}
            
            # Mock Slack client
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance
            
            response = handle_event(ses_event)
            
            # Verify response
            assert response["statusCode"] == 200
            assert "ses event accepted" in response["body"]
            
            # Verify context was saved
            mock_put.assert_called_once()
            
            # Verify Slack notification was sent
            mock_slack_instance.post_message.assert_called_once()
    
    def test_slack_block_actions_routing(self):
        """Test that Slack block_actions events are properly routed"""
        block_actions_event = {
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
                "actions": [
                    {
                        "value": json.dumps({"context_id": "test-context-id"})
                    }
                ]
            })
        }
        
        with patch('src.lambda.router.load_config') as mock_config, \
             patch('src.lambda.router.resolve_slack_credentials') as mock_creds, \
             patch('src.lambda.router.verify_slack_signature') as mock_verify, \
             patch('src.lambda.router.get_context_item') as mock_get, \
             patch('src.lambda.router.generate_reply_draft') as mock_generate, \
             patch('src.lambda.router.reidentify') as mock_reidentify, \
             patch('src.lambda.router.SlackClient') as mock_slack:
            
            # Mock configuration
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
            )
            
            # Mock signature verification
            mock_verify.return_value = True
            
            # Mock Slack credentials
            mock_creds.return_value = {"bot_token": "xoxb-test-token"}
            
            # Mock context retrieval
            mock_get.return_value = {
                "body_redacted": "Test redacted body",
                "pii_map": "{}"
            }
            
            # Mock AI generation
            mock_generate.return_value = "Generated reply draft"
            mock_reidentify.return_value = "Generated reply draft"
            
            # Mock Slack client
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance
            
            response = handle_event(block_actions_event)
            
            # Verify response
            assert response["statusCode"] == 200
            assert response["body"] == '{"ack": true}'
            
            # Verify modal was opened
            mock_slack_instance.open_modal.assert_called_once()
    
    def test_slack_view_submission_routing(self):
        """Test that Slack view_submission events are properly routed"""
        view_submission_event = {
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
                "type": "view_submission",
                "view": {
                    "private_metadata": json.dumps({"context_id": "test-context-id"}),
                    "state": {
                        "values": {
                            "editable_reply_block": {
                                "editable_reply_input": {
                                    "value": "Edited reply text"
                                }
                            }
                        }
                    }
                }
            })
        }
        
        with patch('src.lambda.router.load_config') as mock_config, \
             patch('src.lambda.router.resolve_slack_credentials') as mock_creds, \
             patch('src.lambda.router.verify_slack_signature') as mock_verify, \
             patch('src.lambda.router.get_context_item') as mock_get, \
             patch('src.lambda.router.send_email') as mock_send, \
             patch('src.lambda.router.SlackClient') as mock_slack:
            
            # Mock configuration
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                sender_email_address="support@example.com",
                slack_channel_id="C1234567890"
            )
            
            # Mock signature verification
            mock_verify.return_value = True
            
            # Mock Slack credentials
            mock_creds.return_value = {"bot_token": "xoxb-test-token"}
            
            # Mock context retrieval
            mock_get.return_value = {
                "sender_email": "customer@example.com",
                "subject": "Re: Test Subject"
            }
            
            # Mock Slack client
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance
            
            response = handle_event(view_submission_event)
            
            # Verify response
            assert response["statusCode"] == 200
            assert response["body"] == '{"response_action": "clear"}'
            
            # Verify email was sent
            mock_send.assert_called_once_with(
                sender="support@example.com",
                to_addresses=["customer@example.com"],
                subject="Re: Test Subject",
                body="Edited reply text"
            )
            
            # Verify Slack confirmation was sent
            mock_slack_instance.post_message.assert_called_once()
    
    def test_unknown_event_type(self):
        """Test that unknown event types return appropriate error"""
        unknown_event = {
            "unknown": "event"
        }
        
        with patch('src.lambda.router.load_config') as mock_config:
            mock_config.return_value = MagicMock()
            
            response = handle_event(unknown_event)
            
            # Verify error response
            assert response["statusCode"] == 400
            assert "unrecognized event" in response["body"]
    
    def test_slack_signature_verification_failure(self):
        """Test that failed signature verification returns 401"""
        slack_event = {
            "requestContext": {
                "http": {
                    "method": "POST"
                }
            },
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": "1234567890",
                "X-Slack-Signature": "v0=invalid-signature"
            },
            "body": "payload=" + json.dumps({
                "type": "block_actions"
            })
        }
        
        with patch('src.lambda.router.load_config') as mock_config, \
             patch('src.lambda.router.resolve_slack_credentials') as mock_creds, \
             patch('src.lambda.router.verify_slack_signature') as mock_verify:
            
            # Mock configuration
            mock_config.return_value = MagicMock(
                slack_signing_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
                slack_app_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
            )
            
            # Mock Slack credentials
            mock_creds.return_value = {"signing_secret": "test-secret"}
            
            # Mock signature verification failure
            mock_verify.return_value = False
            
            response = handle_event(slack_event)
            
            # Verify unauthorized response
            assert response["statusCode"] == 401
            assert "unauthorized" in response["body"]
