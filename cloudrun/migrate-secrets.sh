#!/bin/bash

# AWS Secrets Manager to GCP Secrets Manager Migration Script
# This script migrates secrets from AWS to GCP for Cloud Run deployment

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
AWS_REGION="${AWS_REGION:-ap-northeast-1}"

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
    if [[ -z "$PROJECT_ID" ]]; then
        log_error "PROJECT_ID environment variable is required"
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed or not in PATH"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi
    
    # Check GCP credentials
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "GCP credentials not configured. Run 'gcloud auth login' first."
        exit 1
    fi
    
    # Set GCP project
    gcloud config set project "$PROJECT_ID"
}

# Get secret value from AWS Secrets Manager
get_aws_secret() {
    local secret_name="$1"
    local secret_arn="arn:aws:secretsmanager:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):secret:${secret_name}"
    
    log_info "Retrieving secret: $secret_name"
    
    # Try to get the secret value
    local secret_value
    if secret_value=$(aws secretsmanager get-secret-value --secret-id "$secret_arn" --query SecretString --output text 2>/dev/null); then
        echo "$secret_value"
    else
        log_error "Failed to retrieve secret: $secret_name"
        return 1
    fi
}

# Create or update secret in GCP Secrets Manager
set_gcp_secret() {
    local secret_name="$1"
    local secret_value="$2"
    
    log_info "Setting GCP secret: $secret_name"
    
    # Create secret if it doesn't exist
    if ! gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
        log_info "Creating new secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create "$secret_name" \
            --data-file=- \
            --project="$PROJECT_ID" \
            --replication-policy="automatic"
    else
        log_info "Updating existing secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
            --data-file=- \
            --project="$PROJECT_ID"
    fi
}

# Migrate Slack signing secret
migrate_slack_signing_secret() {
    log_info "Migrating Slack signing secret..."
    
    local aws_secret_name="reply-bot/slack/signing-secret"
    local gcp_secret_name="slack-signing-secret-${ENVIRONMENT}"
    
    local secret_value
    if secret_value=$(get_aws_secret "$aws_secret_name"); then
        set_gcp_secret "$gcp_secret_name" "$secret_value"
        log_info "✓ Slack signing secret migrated successfully"
    else
        log_error "✗ Failed to migrate Slack signing secret"
        return 1
    fi
}

# Migrate Slack bot token
migrate_slack_bot_token() {
    log_info "Migrating Slack bot token..."
    
    local aws_secret_name="reply-bot/stg/slack/app-creds"
    local gcp_secret_name="slack-bot-token-${ENVIRONMENT}"
    
    local secret_value
    if secret_value=$(get_aws_secret "$aws_secret_name"); then
        # Extract bot_token from JSON
        local bot_token
        if bot_token=$(echo "$secret_value" | jq -r '.bot_token' 2>/dev/null); then
            if [[ "$bot_token" != "null" && "$bot_token" != "" ]]; then
                set_gcp_secret "$gcp_secret_name" "$bot_token"
                log_info "✓ Slack bot token migrated successfully"
            else
                log_error "✗ Bot token not found in Slack app credentials"
                return 1
            fi
        else
            log_error "✗ Failed to parse Slack app credentials JSON"
            return 1
        fi
    else
        log_error "✗ Failed to migrate Slack bot token"
        return 1
    fi
}

# Migrate OpenAI API key
migrate_openai_api_key() {
    log_info "Migrating OpenAI API key..."
    
    local aws_secret_name="reply-bot/stg/openai/api-key"
    local gcp_secret_name="openai-api-key-${ENVIRONMENT}"
    
    local secret_value
    if secret_value=$(get_aws_secret "$aws_secret_name"); then
        set_gcp_secret "$gcp_secret_name" "$secret_value"
        log_info "✓ OpenAI API key migrated successfully"
    else
        log_error "✗ Failed to migrate OpenAI API key"
        return 1
    fi
}

# Migrate Gmail OAuth credentials
migrate_gmail_oauth() {
    log_info "Migrating Gmail OAuth credentials..."
    
    local aws_secret_name="reply-bot/gmail/oauth"
    local gcp_secret_name="gmail-oauth-${ENVIRONMENT}"
    
    local secret_value
    if secret_value=$(get_aws_secret "$aws_secret_name"); then
        set_gcp_secret "$gcp_secret_name" "$secret_value"
        log_info "✓ Gmail OAuth credentials migrated successfully"
    else
        log_error "✗ Failed to migrate Gmail OAuth credentials"
        return 1
    fi
}

# Verify migrated secrets
verify_secrets() {
    log_info "Verifying migrated secrets..."
    
    local secrets=(
        "slack-signing-secret-${ENVIRONMENT}"
        "slack-bot-token-${ENVIRONMENT}"
        "openai-api-key-${ENVIRONMENT}"
        "gmail-oauth-${ENVIRONMENT}"
    )
    
    local all_verified=true
    
    for secret in "${secrets[@]}"; do
        if gcloud secrets describe "$secret" --project="$PROJECT_ID" &>/dev/null; then
            log_info "✓ $secret exists"
        else
            log_error "✗ $secret not found"
            all_verified=false
        fi
    done
    
    if [[ "$all_verified" == true ]]; then
        log_info "All secrets verified successfully"
        return 0
    else
        log_error "Some secrets verification failed"
        return 1
    fi
}

# Main migration function
main() {
    log_info "Starting AWS to GCP secrets migration..."
    log_info "Project ID: $PROJECT_ID"
    log_info "Environment: $ENVIRONMENT"
    log_info "AWS Region: $AWS_REGION"
    
    validate_env
    
    # Migrate each secret
    migrate_slack_signing_secret
    migrate_slack_bot_token
    migrate_openai_api_key
    migrate_gmail_oauth
    
    # Verify all secrets
    verify_secrets
    
    log_info "Secrets migration completed successfully!"
    log_info "Next steps:"
    log_info "1. Deploy Cloud Run infrastructure: ./cloudrun/deploy.sh"
    log_info "2. Update Lambda environment variables with Cloud Run endpoint"
    log_info "3. Update Slack Request URL to point to Cloud Run service"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [--help]"
        echo ""
        echo "Environment variables:"
        echo "  PROJECT_ID     GCP Project ID (required)"
        echo "  ENVIRONMENT    Environment name (default: staging)"
        echo "  AWS_REGION     AWS region (default: ap-northeast-1)"
        echo ""
        echo "This script migrates secrets from AWS Secrets Manager to GCP Secrets Manager"
        echo "for Cloud Run deployment."
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
