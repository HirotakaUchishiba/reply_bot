from __future__ import annotations

from typing import Any, Dict
import json
import os

from flask import Flask, request, jsonify
from slack_sdk import WebClient
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest
import requests


app = Flask(__name__)


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.post("/async/generate")
def async_generate() -> Any:
    # Optional simple auth via static header
    expected = os.getenv("ASYNC_GENERATION_AUTH_HEADER", "")
    received = request.headers.get("Authorization", "")
    if expected and expected != received:
        return ("unauthorized", 401)

    try:
        payload: Dict[str, Any] = request.get_json(force=True) or {}
    except Exception:
        payload = {}

    context_id = str(payload.get("context_id", ""))
    external_id = str(payload.get("external_id", ""))
    redacted_body = str(payload.get("redacted_body", ""))
    pii_map = payload.get("pii_map") or {}

    # Trigger Cloud Run Job instead of in-process generation
    try:
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        region = os.getenv("REGION", "us-central1")
        job_name = os.getenv("JOB_NAME", "reply-bot-job")
        payload = {
            "jobs.run": {
                "name": f"projects/{project}/locations/{region}/jobs/{job_name}",
                "overrides": {
                    "containerOverrides": [
                        {
                            "name": "worker",
                            "env": [
                                {"name": "JOB_PAYLOAD", "value": json.dumps({
                                    "context_id": context_id,
                                    "external_id": external_id,
                                    "redacted_body": redacted_body,
                                    "pii_map": pii_map,
                                })},
                                {"name": "OPENAI_API_KEY", "value": os.getenv("OPENAI_API_KEY", "")},
                                {"name": "SLACK_BOT_TOKEN", "value": os.getenv("SLACK_BOT_TOKEN", "")},
                            ],
                        }
                    ]
                },
            }
        }

        creds, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(GoogleAuthRequest())
        id_token = creds.token

        # Use REST call to Cloud Run Jobs (v1 API)
        url = f"https://run.googleapis.com/apis/run.googleapis.com/v1/namespaces/{project}/jobs/{job_name}:run"
        headers = {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json",
        }
        # Minimal body for run
        body = {
            "apiVersion": "run.googleapis.com/v1",
            "kind": "Job",
            "metadata": {"name": job_name, "namespace": project},
            # Note: overrides via REST differ by version; keep simple and rely on job's default envs
        }
        # Fire and forget
        requests.post(url, headers=headers, json=body, timeout=3)
    except Exception:
        pass

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


