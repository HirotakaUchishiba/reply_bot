#!/usr/bin/env bash
set -euo pipefail

# Slack Request URL Migration Script
# API Gateway → Cloud Run への移行を自動化

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
AWS_TF_DIR="$PROJECT_ROOT/infra/terraform"

# Default values
GCP_PROJECT_ID=""
GCP_REGION="asia-northeast1"
ENVIRONMENT="staging"
AWS_ACCESS_KEY_ID=""
AWS_SECRET_ACCESS_KEY=""
AUTH_TOKEN=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --gcp-project-id)
            GCP_PROJECT_ID="$2"
            shift 2
            ;;
        --aws-access-key-id)
            AWS_ACCESS_KEY_ID="$2"
            shift 2
            ;;
        --aws-secret-access-key)
            AWS_SECRET_ACCESS_KEY="$2"
            shift 2
            ;;
        --auth-token)
            AUTH_TOKEN="$2"
            shift 2
            ;;
        --region)
            GCP_REGION="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --gcp-project-id ID        GCP Project ID (required)"
            echo "  --aws-access-key-id KEY    AWS Access Key ID (required)"
            echo "  --aws-secret-access-key KEY AWS Secret Access Key (required)"
            echo "  --auth-token TOKEN         Authentication token (required)"
            echo "  --region REGION            GCP Region (default: asia-northeast1)"
            echo "  --environment ENV          Environment (default: staging)"
            echo "  --help                     Show this help message"
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
    
    if [[ -z "$GCP_PROJECT_ID" ]]; then
        missing_params+=("--gcp-project-id")
    fi
    
    if [[ -z "$AWS_ACCESS_KEY_ID" ]]; then
        missing_params+=("--aws-access-key-id")
    fi
    
    if [[ -z "$AWS_SECRET_ACCESS_KEY" ]]; then
        missing_params+=("--aws-secret-access-key")
    fi
    
    if [[ -z "$AUTH_TOKEN" ]]; then
        missing_params+=("--auth-token")
    fi
    
    if [[ ${#missing_params[@]} -gt 0 ]]; then
        log_error "Missing required parameters: ${missing_params[*]}"
        echo "Use --help for usage information"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check terraform
    if ! command -v terraform &> /dev/null; then
        log_error "terraform is not installed. Please install it first."
        exit 1
    fi
    
    # Check docker
    if ! command -v docker &> /dev/null; then
        log_error "docker is not installed. Please install it first."
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Setup GCP project
setup_gcp_project() {
    log_step "Setting up GCP project..."
    
    # Set project
    gcloud config set project "$GCP_PROJECT_ID"
    
    # Enable required APIs
    log_info "Enabling required APIs..."
    gcloud services enable run.googleapis.com
    gcloud services enable secretmanager.googleapis.com
    gcloud services enable artifactregistry.googleapis.com
    
    log_info "GCP project setup completed"
}

# Deploy GCP infrastructure
deploy_gcp_infrastructure() {
    log_step "Deploying GCP infrastructure..."
    
    cd "$GCP_TF_DIR"
    
    # Update staging.tfvars
    cat > staging.tfvars << EOF
# GCP Configuration
gcp_project_id = "$GCP_PROJECT_ID"
gcp_region     = "$GCP_REGION"
environment    = "$ENVIRONMENT"

# AWS Configuration (for DynamoDB access)
aws_access_key_id     = "$AWS_ACCESS_KEY_ID"
aws_secret_access_key = "$AWS_SECRET_ACCESS_KEY"
aws_region           = "ap-northeast-1"
ddb_table_name       = "reply-bot-context-$ENVIRONMENT"

# Authentication
auth_token = "$AUTH_TOKEN"
EOF
    
    # Initialize and apply
    terraform init
    terraform plan -var-file=staging.tfvars
    terraform apply -var-file=staging.tfvars -auto-approve
    
    log_info "GCP infrastructure deployed"
}

# Deploy Cloud Run services
deploy_cloudrun_services() {
    log_step "Deploying Cloud Run services..."
    
    cd "$PROJECT_ROOT/cloudrun"
    
    # Set environment variables
    export PROJECT_ID="$GCP_PROJECT_ID"
    export REGION="$GCP_REGION"
    export ENVIRONMENT="$ENVIRONMENT"
    export AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
    export AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
    export DDB_TABLE_NAME="reply-bot-context-$ENVIRONMENT"
    
    # Deploy
    ./deploy.sh
    
    log_info "Cloud Run services deployed"
}

# Update AWS configuration
update_aws_configuration() {
    log_step "Updating AWS configuration..."
    
    # Get Cloud Run service URL
    cd "$GCP_TF_DIR"
    CLOUD_RUN_URL=$(terraform output -raw cloud_run_service_url)
    ASYNC_ENDPOINT=$(terraform output -raw async_generation_endpoint)
    
    log_info "Cloud Run Service URL: $CLOUD_RUN_URL"
    log_info "Async Generation Endpoint: $ASYNC_ENDPOINT"
    
    # Update AWS staging.tfvars
    cd "$AWS_TF_DIR"
    
    # Backup original file
    cp staging.tfvars staging.tfvars.backup
    
    # Add Cloud Run configuration
    cat >> staging.tfvars << EOF

# Cloud Run async generation configuration
async_generation_endpoint = "$ASYNC_ENDPOINT"
async_generation_auth_header = "Bearer $AUTH_TOKEN"
EOF
    
    # Apply AWS changes
    terraform apply -var-file=staging.tfvars -auto-approve
    
    log_info "AWS configuration updated"
}

# Display next steps
display_next_steps() {
    log_step "Migration completed! Next steps:"
    
    cd "$GCP_TF_DIR"
    CLOUD_RUN_URL=$(terraform output -raw cloud_run_service_url)
    SLACK_REQUEST_URL="$CLOUD_RUN_URL/slack/events"
    
    echo ""
    echo "1. Update Slack App configuration:"
    echo "   - Go to https://api.slack.com/apps"
    echo "   - Select your app"
    echo "   - Update Event Subscriptions Request URL to:"
    echo "     $SLACK_REQUEST_URL"
    echo "   - Update Interactive Components Request URL to:"
    echo "     $SLACK_REQUEST_URL"
    echo ""
    echo "2. Set up secrets in Google Secret Manager:"
    echo "   gcloud secrets versions add slack-signing-secret-$ENVIRONMENT --data-file=<(echo 'your-slack-signing-secret')"
    echo "   gcloud secrets versions add slack-bot-token-$ENVIRONMENT --data-file=<(echo 'your-slack-bot-token')"
    echo "   gcloud secrets versions add openai-api-key-$ENVIRONMENT --data-file=<(echo 'your-openai-api-key')"
    echo ""
    echo "3. Test the integration:"
    echo "   - Send a test message in Slack"
    echo "   - Click '返信文を生成する' button"
    echo "   - Verify modal opens immediately"
    echo "   - Verify AI-generated content appears after a few seconds"
    echo ""
    echo "4. Monitor logs:"
    echo "   gcloud logging read 'resource.type=cloud_run_revision' --limit=50"
    echo ""
}

# Main execution
main() {
    log_info "Starting Slack Request URL migration to Cloud Run..."
    
    validate_params
    check_prerequisites
    setup_gcp_project
    deploy_gcp_infrastructure
    deploy_cloudrun_services
    update_aws_configuration
    display_next_steps
    
    log_info "Migration completed successfully!"
}

# Run main function
main "$@"
