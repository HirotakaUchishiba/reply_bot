"""
Integration tests for Cloud Run components
"""
import json
import pytest
from unittest.mock import patch, MagicMock
import os

# Import Cloud Run components
import sys
sys.path.append('/Users/hirotaka/Desktop/Development/reply_bot/cloudrun/service')
sys.path.append('/Users/hirotaka/Desktop/Development/reply_bot/cloudrun/job_worker')

try:
    from main import app, trigger_cloud_run_job, get_secret, verify_slack_signature
    from worker import main as worker_main, _call_openai, _reidentify_pii, _get_dynamodb_context, _update_slack_modal
    from config import JobWorkerConfig
except ImportError as e:
    pytest.skip(f"Cloud Run components not available: {e}", allow_module_level=True)


class TestCloudRunServiceIntegration:
    """Test Cloud Run service integration scenarios"""

    @pytest.fixture
    def client(self):
        """Create test client for Cloud Run service."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_async_generate_endpoint_integration(self, client):
        """Test async generate endpoint with real payload structure"""
        payload = {
            "context_id": "test-context-123",
            "external_id": "ai-reply-test-context-123",
            "stage": "staging"
        }

        with patch('main.trigger_cloud_run_job', return_value=True) as mock_trigger:
            response = client.post('/async/generate', 
                                 json=payload,
                                 headers={'Content-Type': 'application/json'})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'job_triggered'
            
            # Verify job was triggered with correct parameters
            mock_trigger.assert_called_once_with(
                'test-context-123',
                'ai-reply-test-context-123',
                'staging'
            )

    def test_slack_events_endpoint_integration(self, client):
        """Test Slack events endpoint with real Slack payload"""
        slack_payload = {
            "type": "block_actions",
            "user": {"id": "U1234567890"},
            "trigger_id": "test-trigger-id",
            "actions": [{
                "action_id": "generate_reply_action",
                "value": json.dumps({"context_id": "test-context-456"})
            }]
        }

        with (
            patch('main.verify_slack_signature', return_value=True) as mock_verify,
            patch('main.trigger_cloud_run_job', return_value=True) as mock_trigger
        ):
            response = client.post('/slack/events',
                                 data={'payload': json.dumps(slack_payload)},
                                 content_type='application/x-www-form-urlencoded')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'job_triggered'
            
            # Verify signature was checked
            mock_verify.assert_called_once()
            
            # Verify job was triggered
            mock_trigger.assert_called_once()

    def test_health_endpoint_integration(self, client):
        """Test health endpoint returns proper status"""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'

    @patch('main.run_v2.JobsClient')
    def test_cloud_run_job_trigger_integration(self, mock_client_class):
        """Test Cloud Run job triggering with real GCP client"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_operation = MagicMock()
        mock_client.run_job.return_value = mock_operation
        
        result = trigger_cloud_run_job('test-context', 'test-external', 'staging')
        
        assert result is True
        mock_client.run_job.assert_called_once()
        
        # Verify job parameters
        call_args = mock_client.run_job.call_args
        assert 'test-context' in str(call_args)
        assert 'test-external' in str(call_args)
        assert 'staging' in str(call_args)

    @patch('main.secretmanager.SecretManagerServiceClient')
    def test_secret_retrieval_integration(self, mock_client_class):
        """Test secret retrieval with real GCP Secret Manager client"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = 'test-secret-value'
        mock_client.access_secret_version.return_value = mock_response
        
        result = get_secret('projects/test-project/secrets/test-secret/versions/latest')
        
        assert result == 'test-secret-value'
        mock_client.access_secret_version.assert_called_once()


class TestCloudRunJobWorkerIntegration:
    """Test Cloud Run job worker integration scenarios"""

    def test_worker_main_integration(self):
        """Test worker main function with complete environment"""
        job_payload = {
            "context_id": "test-context-789",
            "external_id": "ai-reply-test-context-789",
            "redacted_body": "Test email content with [PERSON_1]",
            "pii_map": {"[PERSON_1]": "John Doe"}
        }

        env_vars = {
            'OPENAI_API_KEY': 'test-openai-key',
            'SLACK_BOT_TOKEN': 'xoxb-test-token',
            'DDB_TABLE_NAME': 'test-table',
            'JOB_PAYLOAD': json.dumps(job_payload)
        }

        with (
            patch.dict(os.environ, env_vars),
            patch('worker._call_openai', return_value="Generated reply text") as mock_openai,
            patch('worker._update_slack_modal', return_value=True) as mock_update
        ):
            with pytest.raises(SystemExit) as exc_info:
                worker_main()
            
            assert exc_info.value.code == 0
            
            # Verify OpenAI was called
            mock_openai.assert_called_once_with("Test email content with [PERSON_1]", 
                                              JobWorkerConfig(
                                                  openai_api_key='test-openai-key',
                                                  slack_bot_token='xoxb-test-token',
                                                  ddb_table_name='test-table'
                                              ))
            
            # Verify Slack modal was updated
            mock_update.assert_called_once_with(
                'ai-reply-test-context-789',
                'test-context-789',
                'Generated reply text',
                JobWorkerConfig(
                    openai_api_key='test-openai-key',
                    slack_bot_token='xoxb-test-token',
                    ddb_table_name='test-table'
                )
            )

    @patch('urllib.request.urlopen')
    def test_openai_integration(self, mock_urlopen):
        """Test OpenAI API integration with real request structure"""
        # Mock successful OpenAI response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": "Thank you for your inquiry. I will help you with that."
                }
            }]
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="test-token",
            ddb_table_name="test-table"
        )

        result = _call_openai("Test email content", config)
        
        assert result == "Thank you for your inquiry. I will help you with that."
        
        # Verify request was made to OpenAI API
        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        assert request.get_full_url() == "https://api.openai.com/v1/chat/completions"
        assert request.get_method() == "POST"
        
        # Verify request payload
        payload = json.loads(request.data.decode('utf-8'))
        assert payload['model'] == 'gpt-4o-mini'
        assert 'Test email content' in payload['messages'][0]['content']

    @patch('boto3.resource')
    def test_dynamodb_integration(self, mock_boto3):
        """Test DynamoDB integration with real AWS client"""
        # Mock DynamoDB response
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'context_id': 'test-context-123',
                'body_redacted': 'Test email content with [PERSON_1]',
                'pii_map': '{"[PERSON_1]": "John Doe"}',
                'sender_email': 'test@example.com',
                'subject': 'Test Subject'
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

        result = _get_dynamodb_context("test-context-123", config)
        
        assert result['context_id'] == 'test-context-123'
        assert result['body_redacted'] == 'Test email content with [PERSON_1]'
        assert result['sender_email'] == 'test@example.com'
        
        # Verify DynamoDB was called correctly
        mock_table.get_item.assert_called_once_with(
            Key={'context_id': 'test-context-123'}
        )

    @patch('slack_sdk.WebClient')
    def test_slack_modal_update_integration(self, mock_webclient):
        """Test Slack modal update integration with real Slack client"""
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client

        config = JobWorkerConfig(
            openai_api_key="test-key",
            slack_bot_token="xoxb-test-token",
            ddb_table_name="test-table"
        )

        result = _update_slack_modal(
            "ai-reply-test-context-123",
            "test-context-123", 
            "Generated reply text",
            config
        )
        
        assert result is True
        
        # Verify Slack client was called correctly
        mock_client.views_update.assert_called_once()
        call_args = mock_client.views_update.call_args
        assert call_args[1]['external_id'] == 'ai-reply-test-context-123'
        assert 'Generated reply text' in call_args[1]['view']['blocks'][1]['element']['initial_value']

    def test_pii_reidentification_integration(self):
        """Test PII reidentification with real data"""
        text = "Hello [PERSON_1], your email [EMAIL_1] has been confirmed. Please contact us at [PHONE_1]."
        pii_map = {
            "[PERSON_1]": "John Doe",
            "[EMAIL_1]": "john.doe@example.com",
            "[PHONE_1]": "+1-555-123-4567"
        }
        
        result = _reidentify_pii(text, pii_map)
        
        expected = "Hello John Doe, your email john.doe@example.com has been confirmed. Please contact us at +1-555-123-4567."
        assert result == expected

    def test_error_handling_integration(self):
        """Test error handling in worker integration"""
        # Test with missing environment variables
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                worker_main()
            assert exc_info.value.code == 1

        # Test with invalid job payload
        env_vars = {
            'OPENAI_API_KEY': 'test-key',
            'SLACK_BOT_TOKEN': 'test-token',
            'DDB_TABLE_NAME': 'test-table',
            'JOB_PAYLOAD': 'invalid-json'
        }
        
        with patch.dict(os.environ, env_vars):
            with pytest.raises(SystemExit) as exc_info:
                worker_main()
            assert exc_info.value.code == 1
