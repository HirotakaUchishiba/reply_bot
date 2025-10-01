#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_ID=${PROJECT_ID:-"$(gcloud config get-value project 2>/dev/null)"}
REGION=${REGION:-"asia-northeast1"}
ENVIRONMENT=${ENVIRONMENT:-"staging"}
REPO_NAME=${REPO_NAME:-"reply-bot"}

SERVICE_NAME="reply-bot-slack-events-${ENVIRONMENT}"
JOB_NAME="reply-bot-generator-${ENVIRONMENT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate required environment variables
validate_env() {
    local missing_vars=()
    
    if [[ -z "${PROJECT_ID:-}" ]]; then
        missing_vars+=("PROJECT_ID")
    fi
    
    if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
        missing_vars+=("AWS_ACCESS_KEY_ID")
    fi
    
    if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        missing_vars+=("AWS_SECRET_ACCESS_KEY")
    fi
    
    if [[ -z "${DDB_TABLE_NAME:-}" ]]; then
        missing_vars+=("DDB_TABLE_NAME")
    fi
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables: ${missing_vars[*]}"
        log_error "Please set these variables before running the script"
        exit 1
    fi
}

# Enable required APIs
enable_apis() {
    log_info "Enabling required GCP APIs..."
    gcloud services enable \
        run.googleapis.com \
        cloudbuild.googleapis.com \
        artifactregistry.googleapis.com \
        secretmanager.googleapis.com \
        --project="${PROJECT_ID}"
}

# Configure Docker for Artifact Registry
configure_docker() {
    log_info "Configuring Docker for Artifact Registry..."
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
}

# Build and push Docker images
build_and_push_images() {
    local image_tag="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
    
    # Build service image
    log_info "Building service image..."
    cd cloudrun/service
    docker build -t "${image_tag}/slack-events:latest" .
    docker push "${image_tag}/slack-events:latest"
    cd ../..
    
    # Build job image
    log_info "Building job image..."
    cd cloudrun/job_worker
    docker build -t "${image_tag}/reply-generator:latest" .
    docker push "${image_tag}/reply-generator:latest"
    cd ../..
}

# Deploy using Terraform
deploy_infrastructure() {
    log_info "Deploying infrastructure with Terraform..."
    cd infra/terraform/gcp
    
    # Initialize Terraform if needed
    if [[ ! -d ".terraform" ]]; then
        terraform init
    fi
    
    # Plan and apply
    terraform plan -var-file="${ENVIRONMENT}.tfvars" -out=tfplan
    terraform apply tfplan
    
    cd ../../..
}

# Update secrets
update_secrets() {
    log_info "Updating secrets..."
    
    # Update Slack signing secret
    if [[ -n "${SLACK_SIGNING_SECRET:-}" ]]; then
        echo -n "${SLACK_SIGNING_SECRET}" | gcloud secrets versions add "slack-signing-secret-${ENVIRONMENT}" --data-file=- --project="${PROJECT_ID}"
    fi
    
    # Update Slack bot token
    if [[ -n "${SLACK_BOT_TOKEN:-}" ]]; then
        echo -n "${SLACK_BOT_TOKEN}" | gcloud secrets versions add "slack-bot-token-${ENVIRONMENT}" --data-file=- --project="${PROJECT_ID}"
    fi
    
    # Update OpenAI API key
    if [[ -n "${OPENAI_API_KEY:-}" ]]; then
        echo -n "${OPENAI_API_KEY}" | gcloud secrets versions add "openai-api-key-${ENVIRONMENT}" --data-file=- --project="${PROJECT_ID}"
    fi
}

# Get service URL
get_service_url() {
    local url
    url=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
    echo "${url}"
}

# Main deployment function
main() {
    log_info "Starting deployment of Reply Bot Cloud Run components..."
    log_info "Project: ${PROJECT_ID}"
    log_info "Region: ${REGION}"
    log_info "Environment: ${ENVIRONMENT}"
    
    validate_env
    enable_apis
    configure_docker
    build_and_push_images
    deploy_infrastructure
    update_secrets
    
    local service_url
    service_url=$(get_service_url)
    
    log_info "Deployment completed successfully!"
    log_info "Service URL: ${service_url}"
    log_info ""
    log_info "Next steps:"
    log_info "1. Update Slack Request URL to: ${service_url}/slack/events"
    log_info "2. Update Lambda environment variables:"
    log_info "   ASYNC_GENERATION_ENDPOINT=${service_url}/async/generate"
    log_info "   ASYNC_GENERATION_AUTH_HEADER=Bearer your-auth-token"
}

# Run main function
main "$@"

