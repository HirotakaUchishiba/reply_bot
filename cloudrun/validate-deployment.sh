#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_ID=${PROJECT_ID:-"$(gcloud config get-value project 2>/dev/null)"}
REGION=${REGION:-"asia-northeast1"}
ENVIRONMENT=${ENVIRONMENT:-"staging"}

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

# Validate environment variables
validate_env() {
    local missing_vars=()
    
    if [[ -z "${PROJECT_ID:-}" ]]; then
        missing_vars+=("PROJECT_ID")
    fi
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables: ${missing_vars[*]}"
        exit 1
    fi
}

# Check if secrets exist in GCP Secret Manager
check_secrets() {
    log_info "Checking GCP Secret Manager secrets..."
    
    local secrets=(
        "slack-signing-secret-${ENVIRONMENT}"
        "slack-bot-token-${ENVIRONMENT}"
        "openai-api-key-${ENVIRONMENT}"
        "gmail-oauth-${ENVIRONMENT}"
    )
    
    local all_secrets_exist=true
    
    for secret in "${secrets[@]}"; do
        if gcloud secrets describe "${secret}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
            log_info "✓ Secret '${secret}' exists"
        else
            log_error "✗ Secret '${secret}' not found"
            all_secrets_exist=false
        fi
    done
    
    if [[ "$all_secrets_exist" == true ]]; then
        log_info "All secrets are available"
        return 0
    else
        log_error "Some secrets are missing"
        return 1
    fi
}

# Check if Cloud Run service exists and is healthy
check_cloud_run_service() {
    log_info "Checking Cloud Run service..."
    
    if ! gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        log_error "Cloud Run service '${SERVICE_NAME}' not found"
        return 1
    fi
    
    local service_url
    service_url=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
    
    log_info "Service URL: ${service_url}"
    
    # Test health endpoint
    log_info "Testing health endpoint..."
    if curl -f -s "${service_url}/health" >/dev/null; then
        log_info "Health check passed"
    else
        log_error "Health check failed"
        return 1
    fi
    
    return 0
}

# Check if Cloud Run job exists
check_cloud_run_job() {
    log_info "Checking Cloud Run job..."
    
    if ! gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        log_error "Cloud Run job '${JOB_NAME}' not found"
        return 1
    fi
    
    log_info "Cloud Run job exists"
    return 0
}

# Check if secrets exist
check_secrets() {
    log_info "Checking secrets..."
    
    local secrets=(
        "slack-signing-secret-${ENVIRONMENT}"
        "slack-bot-token-${ENVIRONMENT}"
        "openai-api-key-${ENVIRONMENT}"
    )
    
    for secret in "${secrets[@]}"; do
        if ! gcloud secrets describe "${secret}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
            log_error "Secret '${secret}' not found"
            return 1
        fi
        
        # Check if secret has a version
        if ! gcloud secrets versions list "${secret}" --project="${PROJECT_ID}" --limit=1 --format="value(name)" | grep -q .; then
            log_warn "Secret '${secret}' exists but has no versions"
        else
            log_info "Secret '${secret}' exists and has versions"
        fi
    done
    
    return 0
}

# Check if Artifact Registry repository exists
check_artifact_registry() {
    log_info "Checking Artifact Registry repository..."
    
    local repo_name="reply-bot"
    
    if ! gcloud artifacts repositories describe "${repo_name}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        log_error "Artifact Registry repository '${repo_name}' not found"
        return 1
    fi
    
    log_info "Artifact Registry repository exists"
    
    # Check if images exist
    local images=("slack-events" "job-worker")
    for image in "${images[@]}"; do
        if gcloud artifacts docker images list "${REGION}-docker.pkg.dev/${PROJECT_ID}/${repo_name}/${image}" --include-tags --limit=1 >/dev/null 2>&1; then
            log_info "Docker image '${image}' exists"
        else
            log_warn "Docker image '${image}' not found"
        fi
    done
    
    return 0
}

# Test async generation endpoint
test_async_endpoint() {
    log_info "Testing async generation endpoint..."
    
    local service_url
    service_url=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
    
    local test_payload='{
        "context_id": "test-context-id",
        "external_id": "ai-reply-test-context-id",
        "stage": "'${ENVIRONMENT}'"
    }'
    
    # Test with curl (expect 401 without auth token, which is expected)
    local response_code
    response_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${service_url}/async/generate" \
        -H "Content-Type: application/json" \
        -d "${test_payload}")
    
    if [[ "${response_code}" == "401" ]]; then
        log_info "Async endpoint responds correctly (401 without auth)"
    elif [[ "${response_code}" == "200" ]]; then
        log_info "Async endpoint responds correctly (200 with auth)"
    else
        log_warn "Async endpoint returned unexpected status: ${response_code}"
    fi
    
    return 0
}

# Main validation function
main() {
    log_info "Starting deployment validation..."
    log_info "Project: ${PROJECT_ID}"
    log_info "Region: ${REGION}"
    log_info "Environment: ${ENVIRONMENT}"
    
    validate_env
    
    local failed_checks=0
    
    if ! check_cloud_run_service; then
        ((failed_checks++))
    fi
    
    if ! check_cloud_run_job; then
        ((failed_checks++))
    fi
    
    if ! check_secrets; then
        ((failed_checks++))
    fi
    
    if ! check_artifact_registry; then
        ((failed_checks++))
    fi
    
    if ! test_async_endpoint; then
        ((failed_checks++))
    fi
    
    if [[ ${failed_checks} -eq 0 ]]; then
        log_info "All validation checks passed!"
        log_info ""
        log_info "Deployment is ready for use."
        log_info "Next steps:"
        log_info "1. Update Slack Request URL"
        log_info "2. Update Lambda environment variables"
        log_info "3. Test end-to-end workflow"
    else
        log_error "Validation failed with ${failed_checks} errors"
        exit 1
    fi
}

# Run main function
main "$@"
