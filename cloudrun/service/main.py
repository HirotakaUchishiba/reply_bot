"""
Cloud Run HTTP Service for Slack Events
Receives Slack events and triggers Cloud Run Jobs for async processing
"""
import json
import os
import logging
from typing import Dict, Any
from flask import Flask, request, jsonify
import google.cloud.run_v2 as run_v2
from google.cloud import secretmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment variables
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("GCP_REGION", "asia-northeast1")
JOB_NAME = os.getenv("CLOUD_RUN_JOB_NAME", "reply-bot-generator")
SERVICE_ACCOUNT = os.getenv("SERVICE_ACCOUNT_EMAIL")
SLACK_SIGNING_SECRET_NAME = os.getenv("SLACK_SIGNING_SECRET_NAME", "slack-signing-secret")
SLACK_BOT_TOKEN_SECRET_NAME = os.getenv("SLACK_BOT_TOKEN_SECRET_NAME", "slack-bot-token-staging")


def get_secret(secret_name: str) -> str:
    """Get secret from Google Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error(f"Failed to get secret {secret_name}: {e}")
        raise


def get_slack_bot_token() -> str:
    """Get Slack bot token from Secret Manager"""
    try:
        return get_secret(SLACK_BOT_TOKEN_SECRET_NAME)
    except Exception as e:
        logger.error(f"Failed to get Slack bot token: {e}")
        return ""


def open_slack_modal(trigger_id: str, context_id: str) -> bool:
    """Open Slack modal for reply generation"""
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        bot_token = get_slack_bot_token()
        if not bot_token:
            logger.error("Slack bot token not available")
            return False
        
        client = WebClient(token=bot_token)
        
        # Create modal view
        view = {
            "type": "modal",
            "callback_id": "ai_reply_modal_submission",
            "private_metadata": json.dumps({"context_id": context_id}),
            "title": {"type": "plain_text", "text": "AI返信アシスタント"},
            "submit": {"type": "plain_text", "text": "この内容でメールを送信"},
            "close": {"type": "plain_text", "text": "閉じる"},
            "external_id": f"ai-reply-{context_id}",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "返信文案の確認・編集"},
                },
                {
                    "type": "input",
                    "block_id": "editable_reply_block",
                    "label": {
                        "type": "plain_text",
                        "text": "以下の返信文案を編集し、送信してください。",
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "editable_reply_input",
                        "multiline": True,
                        "initial_value": "AIが返信文案を生成中です。しばらくお待ちください...",
                    },
                },
            ],
        }
        
        client.views_open(trigger_id=trigger_id, view=view)
        logger.info(f"Opened Slack modal for context_id: {context_id}")
        return True
        
    except SlackApiError as e:
        logger.error(f"Slack API error: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to open Slack modal: {e}")
        return False


def verify_slack_signature(timestamp: str, signature: str, body: bytes) -> bool:
    """Verify Slack request signature"""
    try:
        import hmac
        import hashlib
        import time
        
        signing_secret = get_secret(SLACK_SIGNING_SECRET_NAME)
        
        # Check timestamp (within 5 minutes)
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("Request timestamp too old")
            return False
            
        # Create signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_signature = 'v0=' + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


def trigger_cloud_run_job(context_id: str, external_id: str, stage: str) -> bool:
    """Trigger Cloud Run Job for async processing"""
    try:
        client = run_v2.JobsClient()
        job_name = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"
        
        # Prepare job execution request
        request = run_v2.RunJobRequest(
            name=job_name,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        env=[
                            run_v2.EnvVar(name="CONTEXT_ID", value=context_id),
                            run_v2.EnvVar(name="EXTERNAL_ID", value=external_id),
                            run_v2.EnvVar(name="STAGE", value=stage),
                        ]
                    )
                ]
            )
        )
        
        # Execute job
        operation = client.run_job(request=request)
        logger.info(f"Triggered Cloud Run Job for context_id: {context_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to trigger Cloud Run Job: {e}")
        return False


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route("/async/generate", methods=["POST"])
def async_generate():
    """Handle async generation requests from Lambda"""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        context_id = data.get("context_id")
        external_id = data.get("external_id")
        stage = data.get("stage")
        
        if not all([context_id, external_id, stage]):
            return jsonify({"error": "Missing required fields"}), 400
            
        # Trigger Cloud Run Job
        success = trigger_cloud_run_job(context_id, external_id, stage)
        
        if success:
            return jsonify({"status": "job_triggered"}), 200
        else:
            return jsonify({"error": "Failed to trigger job"}), 500
            
    except Exception as e:
        logger.error(f"Error in async_generate: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle Slack events (URL verification and interactions)"""
    try:
        # Get headers
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        
        # Get request body
        body = request.get_data()
        
        # Verify signature
        if not verify_slack_signature(timestamp, signature, body):
            logger.warning("Invalid Slack signature")
            return jsonify({"error": "Unauthorized"}), 401
            
        # Parse request data
        if request.content_type == "application/x-www-form-urlencoded":
            # Slack interactive components
            form_data = request.form
            payload_str = form_data.get("payload", "{}")
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                return jsonify({"error": "Invalid payload"}), 400
        else:
            # Slack events API
            try:
                payload = request.get_json()
            except Exception:
                return jsonify({"error": "Invalid JSON"}), 400
                
        # Handle URL verification challenge
        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge")
            if challenge:
                return challenge, 200
                
        # Handle interactive components (button clicks)
        if payload.get("type") == "block_actions":
            actions = payload.get("actions", [])
            if actions:
                action = actions[0]
                if action.get("action_id") == "generate_reply_action":
                    # Extract context_id from button value
                    try:
                        value_data = json.loads(action.get("value", "{}"))
                        context_id = value_data.get("context_id", "")
                        trigger_id = payload.get("trigger_id", "")
                        external_id = f"ai-reply-{context_id}" if context_id else ""
                        stage = os.getenv("STAGE", "staging")
                        
                        if context_id and trigger_id:
                            # Open modal immediately
                            modal_success = open_slack_modal(trigger_id, context_id)
                            if not modal_success:
                                logger.error("Failed to open Slack modal")
                                return jsonify({"error": "Failed to open modal"}), 500
                            
                            # Trigger Cloud Run Job for async generation
                            job_success = trigger_cloud_run_job(context_id, external_id, stage)
                            if job_success:
                                return jsonify({"status": "modal_opened_and_job_triggered"}), 200
                            else:
                                logger.warning("Modal opened but job trigger failed")
                                return jsonify({"status": "modal_opened"}), 200
                        else:
                            return jsonify({"error": "Missing context_id or trigger_id"}), 400
                    except Exception as e:
                        logger.error(f"Error processing block_actions: {e}")
                        return jsonify({"error": "Processing failed"}), 500
                        
        # Default response
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"Error in slack_events: {e}")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # Validate required environment variables
    required_vars = ["GCP_PROJECT_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        exit(1)
        
    # Run the app
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
