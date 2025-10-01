#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID=${PROJECT_ID:-"$(gcloud config get-value project 2>/dev/null)"}
REGION=${REGION:-"us-central1"}

SERVICE_NAME=${SERVICE_NAME:-"reply-bot-async"}
JOB_NAME=${JOB_NAME:-"reply-bot-job"}

# Build & deploy service
gcloud builds submit cloudrun/service --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"
gcloud run deploy "${SERVICE_NAME}" \
  --image "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN:-}" \
  --set-env-vars "ASYNC_GENERATION_AUTH_HEADER=${ASYNC_GENERATION_AUTH_HEADER:-}" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars "REGION=${REGION}" \
  --set-env-vars "JOB_NAME=${JOB_NAME}"

# Build & deploy job
gcloud builds submit cloudrun/job_worker --tag "gcr.io/${PROJECT_ID}/${JOB_NAME}:latest"
gcloud run jobs delete "${JOB_NAME}" --region "${REGION}" --quiet || true
gcloud run jobs create "${JOB_NAME}" \
  --image "gcr.io/${PROJECT_ID}/${JOB_NAME}:latest" \
  --region "${REGION}" \
  --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY:-}" \
  --set-env-vars "SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN:-}"

echo "Deployed service ${SERVICE_NAME} and job ${JOB_NAME} in ${PROJECT_ID}/${REGION}"

