#!/usr/bin/env bash
set -euo pipefail

# Slack App Configuration Update Script
# Updates Request URLs to point to Cloud Run service

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GCP_TF_DIR="$PROJECT_ROOT/infra/terraform/gcp"

# Default values
SLACK_APP_ID=""
SLACK_CLIENT_ID=""
SLACK_CLIENT_SECRET=""
ENVIRONMENT="staging"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --slack-app-id)
            SLACK_APP_ID="$2"
            shift 2
            ;;
        --slack-client-id)
            SLACK_CLIENT_ID="$2"
            shift 2
            ;;
        --slack-client-secret)
            SLACK_CLIENT_SECRET="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --slack-app-id ID          Slack App ID (required)"
            echo "  --slack-client-id ID       Slack Client ID (required)"
            echo "  --slack-client-secret SECRET Slack Client Secret (required)"
            echo "  --environment ENV          Environment (default: staging)"
            echo "  --help                     Show this help message"
            echo ""
            echo "Note: This script requires manual intervention to update Slack app settings."
            echo "It will display the URLs that need to be updated in the Slack API dashboard."
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required parameters
validate_params() {
    local missing_params=()
    
    if [[ -z "$SLACK_APP_ID" ]]; then
        missing_params+=("--slack-app-id")
    fi
    
    if [[ -z "$SLACK_CLIENT_ID" ]]; then
        missing_params+=("--slack-client-id")
    fi
    
    if [[ -z "$SLACK_CLIENT_SECRET" ]]; then
        missing_params+=("--slack-client-secret")
    fi
    
    if [[ ${#missing_params[@]} -gt 0 ]]; then
        log_error "Missing required parameters: ${missing_params[*]}"
        echo "Use --help for usage information"
        exit 1
    fi
}

# Get Cloud Run service URL
get_cloudrun_url() {
    log_step "Getting Cloud Run service URL..."
    
    cd "$GCP_TF_DIR"
    
    if [[ ! -f "staging.tfvars" ]]; then
        log_error "staging.tfvars not found. Please run the migration script first."
        exit 1
    fi
    
    # Get the URL from Terraform output
    CLOUD_RUN_URL=$(terraform output -raw cloud_run_service_url 2>/dev/null || echo "")
    
    if [[ -z "$CLOUD_RUN_URL" ]]; then
        log_error "Failed to get Cloud Run service URL. Make sure GCP infrastructure is deployed."
        exit 1
    fi
    
    SLACK_REQUEST_URL="$CLOUD_RUN_URL/slack/events"
    
    log_info "Cloud Run Service URL: $CLOUD_RUN_URL"
    log_info "Slack Request URL: $SLACK_REQUEST_URL"
}

# Display manual update instructions
display_update_instructions() {
    log_step "Manual Slack App Configuration Update Required"
    
    echo ""
    echo "Please follow these steps to update your Slack app configuration:"
    echo ""
    echo "1. Go to the Slack API dashboard:"
    echo "   https://api.slack.com/apps"
    echo ""
    echo "2. Select your app (App ID: $SLACK_APP_ID)"
    echo ""
    echo "3. Update Event Subscriptions:"
    echo "   - Go to 'Event Subscriptions' in the left sidebar"
    echo "   - Set 'Request URL' to:"
    echo "     $SLACK_REQUEST_URL"
    echo "   - Verify the URL (should show 'Verified' with a green checkmark)"
    echo ""
    echo "4. Update Interactive Components:"
    echo "   - Go to 'Interactive Components' in the left sidebar"
    echo "   - Set 'Request URL' to:"
    echo "     $SLACK_REQUEST_URL"
    echo ""
    echo "5. Update OAuth & Permissions (if needed):"
    echo "   - Go to 'OAuth & Permissions' in the left sidebar"
    echo "   - Verify the following scopes are present:"
    echo "     - chat:write"
    echo "     - views:write"
    echo "     - views:read"
    echo "     - users:read"
    echo ""
    echo "6. Save all changes"
    echo ""
    echo "7. Test the integration:"
    echo "   - Send a test message in your Slack workspace"
    echo "   - Click the '返信文を生成する' button"
    echo "   - Verify the modal opens immediately"
    echo "   - Verify AI-generated content appears after a few seconds"
    echo ""
}

# Test the integration
test_integration() {
    log_step "Testing Cloud Run service..."
    
    # Test health endpoint
    HEALTH_URL="$CLOUD_RUN_URL/health"
    log_info "Testing health endpoint: $HEALTH_URL"
    
    if curl -s -f "$HEALTH_URL" > /dev/null; then
        log_info "Health check passed"
    else
        log_warn "Health check failed. Service might not be ready yet."
    fi
    
    # Test Slack events endpoint (should return 400 for invalid request)
    log_info "Testing Slack events endpoint..."
    RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$SLACK_REQUEST_URL" \
        -H "Content-Type: application/json" \
        -d '{"type":"test"}')
    
    if [[ "$RESPONSE" == "400" ]]; then
        log_info "Slack events endpoint is responding correctly (400 for invalid request)"
    else
        log_warn "Unexpected response from Slack events endpoint: $RESPONSE"
    fi
}

# Display rollback instructions
display_rollback_instructions() {
    log_step "Rollback Instructions (if needed)"
    
    echo ""
    echo "If you need to rollback to the previous API Gateway setup:"
    echo ""
    echo "1. Update Slack App configuration:"
    echo "   - Go to https://api.slack.com/apps"
    echo "   - Select your app"
    echo "   - Update Event Subscriptions Request URL to:"
    echo "     https://4a9u5q0bt1.execute-api.ap-northeast-1.amazonaws.com/slack/events"
    echo "   - Update Interactive Components Request URL to the same URL"
    echo ""
    echo "2. Update AWS configuration:"
    echo "   cd $PROJECT_ROOT/infra/terraform"
    echo "   # Remove or comment out async_generation_endpoint in staging.tfvars"
    echo "   terraform apply -var-file=staging.tfvars"
    echo ""
}

# Main execution
main() {
    log_info "Starting Slack app configuration update..."
    
    validate_params
    get_cloudrun_url
    display_update_instructions
    test_integration
    display_rollback_instructions
    
    log_info "Slack app configuration update completed!"
    log_info "Please follow the manual steps above to complete the migration."
}

# Run main function
main "$@"
