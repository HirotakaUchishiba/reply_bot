"""Unit tests for Cloud Run Job worker."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from worker import (
    _call_openai,
    _reidentify_pii,
    _get_dynamodb_context,
    _update_slack_modal,
    main,
)
from config import JobWorkerConfig


class TestCallOpenAI:
    """Test OpenAI API calls."""

    def test_empty_redacted_body(self):
        """Test with empty redacted body."""
        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )
        result = _call_openai("", config)
        assert result == ""

    def test_no_api_key(self):
        """Test with no API key."""
        config = JobWorkerConfig(
            openai_api_key="",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )
        result = _call_openai("test body", config)
        assert result == ""

    @patch('urllib.request.urlopen')
    def test_successful_generation(self, mock_urlopen):
        """Test successful OpenAI generation."""
        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": "Generated reply text"
                }
            }]
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )

        result = _call_openai("test body", config)
        assert result == "Generated reply text"

    @patch('urllib.request.urlopen')
    def test_api_error(self, mock_urlopen):
        """Test OpenAI API error."""
        mock_urlopen.side_effect = Exception("API Error")

        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )

        result = _call_openai("test body", config)
        assert result == ""


class TestReidentifyPII:
    """Test PII reidentification."""

    def test_no_pii_map(self):
        """Test with no PII map."""
        result = _reidentify_pii("test text", {})
        assert result == "test text"

    def test_with_pii_map(self):
        """Test with PII map."""
        text = "Hello [PERSON_1], your email [EMAIL_1] is confirmed."
        pii_map = {
            "[PERSON_1]": "John Doe",
            "[EMAIL_1]": "john@example.com"
        }
        result = _reidentify_pii(text, pii_map)
        expected = (
            "Hello John Doe, your email john@example.com is confirmed."
        )
        assert result == expected


class TestGetDynamoDBContext:
    """Test DynamoDB context retrieval."""

    def test_no_context_id(self):
        """Test with no context ID."""
        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )
        result = _get_dynamodb_context("", config)
        assert result == {}

    @patch('boto3.resource')
    def test_successful_retrieval(self, mock_boto3):
        """Test successful DynamoDB retrieval."""
        # Mock DynamoDB response
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'context_id': 'test-id',
                'body_redacted': 'test body',
                'pii_map': '{"[PERSON_1]": "John"}'
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.return_value = mock_dynamodb

        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )

        result = _get_dynamodb_context("test-id", config)
        assert result['context_id'] == 'test-id'
        assert result['body_redacted'] == 'test body'

    @patch('boto3.resource')
    def test_dynamodb_error(self, mock_boto3):
        """Test DynamoDB error."""
        mock_boto3.side_effect = Exception("DynamoDB Error")

        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )

        result = _get_dynamodb_context("test-id", config)
        assert result == {}


class TestUpdateSlackModal:
    """Test Slack modal updates."""

    def test_no_bot_token(self):
        """Test with no bot token."""
        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="",
            ddb_table_name="test-table"
        )
        result = _update_slack_modal(
            "test-id", "context-id", "test text", config
        )
        assert result is False

    def test_no_external_id(self):
        """Test with no external ID."""
        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )
        result = _update_slack_modal("", "context-id", "test text", config)
        assert result is False

    @patch('slack_sdk.WebClient')
    def test_successful_update(self, mock_webclient):
        """Test successful Slack modal update."""
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client

        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )

        result = _update_slack_modal(
            "test-id", "context-id", "test text", config
        )
        assert result is True
        mock_client.views_update.assert_called_once()

    @patch('slack_sdk.WebClient')
    def test_slack_api_error(self, mock_webclient):
        """Test Slack API error."""
        from slack_sdk.errors import SlackApiError
        mock_client = MagicMock()
        mock_client.views_update.side_effect = SlackApiError("API Error", {})
        mock_webclient.return_value = mock_client

        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )

        result = _update_slack_modal(
            "test-id", "context-id", "test text", config
        )
        assert result is False


class TestMain:
    """Test main function."""

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'SLACK_BOT_TOKEN': 'test-token',
        'DDB_TABLE_NAME': 'test-table',
        'JOB_PAYLOAD': json.dumps({
            'context_id': 'test-context',
            'external_id': 'test-external',
            'redacted_body': 'test body',
            'pii_map': {}
        })
    })
    @patch('worker._call_openai')
    @patch('worker._update_slack_modal')
    def test_successful_execution(self, mock_update, mock_call):
        """Test successful main execution."""
        mock_call.return_value = "Generated text"
        mock_update.return_value = True

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': '',
        'SLACK_BOT_TOKEN': 'test-token',
        'DDB_TABLE_NAME': 'test-table',
    })
    def test_missing_config(self):
        """Test with missing configuration."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'SLACK_BOT_TOKEN': 'test-token',
        'DDB_TABLE_NAME': 'test-table',
        'JOB_PAYLOAD': json.dumps({
            'context_id': '',
            'external_id': 'test-external',
        })
    })
    def test_missing_context_id(self):
        """Test with missing context ID."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
