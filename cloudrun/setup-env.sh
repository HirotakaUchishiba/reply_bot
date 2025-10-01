#!/usr/bin/env bash
set -euo pipefail

# Configuration setup script for Cloud Run deployment
# This script helps set up environment variables and configuration files

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

# Interactive setup
interactive_setup() {
    log_info "Setting up Cloud Run deployment configuration..."
    
    # Get GCP project ID
    local project_id
    project_id=$(gcloud config get-value project 2>/dev/null || echo "")
    if [[ -z "${project_id}" ]]; then
        read -p "Enter GCP Project ID: " project_id
    else
        read -p "Enter GCP Project ID [${project_id}]: " input_project_id
        project_id=${input_project_id:-${project_id}}
    fi
    
    # Get environment
    local environment
    read -p "Enter environment [staging]: " environment
    environment=${environment:-staging}
    
    # Get region
    local region
    read -p "Enter GCP region [asia-northeast1]: " region
    region=${region:-asia-northeast1}
    
    # Get AWS credentials
    local aws_access_key_id
    read -p "Enter AWS Access Key ID: " aws_access_key_id
    
    local aws_secret_access_key
    read -s -p "Enter AWS Secret Access Key: " aws_secret_access_key
    echo
    
    local aws_region
    read -p "Enter AWS region [ap-northeast-1]: " aws_region
    aws_region=${aws_region:-ap-northeast-1}
    
    # Get DynamoDB table name
    local ddb_table_name
    read -p "Enter DynamoDB table name [reply-bot-context-${environment}]: " ddb_table_name
    ddb_table_name=${ddb_table_name:-reply-bot-context-${environment}}
    
    # Generate auth token
    local auth_token
    auth_token=$(openssl rand -hex 32 2>/dev/null || echo "manual-token-$(date +%s)")
    
    # Create tfvars file
    local tfvars_file="infra/terraform/gcp/${environment}.tfvars"
    log_info "Creating ${tfvars_file}..."
    
    cat > "${tfvars_file}" << EOF
# GCP Configuration
gcp_project_id = "${project_id}"
gcp_region     = "${region}"
environment    = "${environment}"

# AWS Configuration (for DynamoDB access)
aws_access_key_id     = "${aws_access_key_id}"
aws_secret_access_key = "${aws_secret_access_key}"
aws_region           = "${aws_region}"
ddb_table_name       = "${ddb_table_name}"

# Authentication
auth_token = "${auth_token}"
EOF
    
    # Create environment file for deployment
    local env_file=".env.${environment}"
    log_info "Creating ${env_file}..."
    
    cat > "${env_file}" << EOF
# Cloud Run Deployment Environment Variables
export PROJECT_ID="${project_id}"
export REGION="${region}"
export ENVIRONMENT="${environment}"
export AWS_ACCESS_KEY_ID="${aws_access_key_id}"
export AWS_SECRET_ACCESS_KEY="${aws_secret_access_key}"
export DDB_TABLE_NAME="${ddb_table_name}"
export AUTH_TOKEN="${auth_token}"

# Optional: Set these if you want to update secrets during deployment
# export SLACK_SIGNING_SECRET="your-slack-signing-secret"
# export SLACK_BOT_TOKEN="xoxb-your-bot-token"
# export OPENAI_API_KEY="sk-your-openai-key"
EOF
    
    log_info "Configuration files created:"
    log_info "  - ${tfvars_file}"
    log_info "  - ${env_file}"
    log_info ""
    log_info "Next steps:"
    log_info "1. Review and edit ${tfvars_file} if needed"
    log_info "2. Source the environment file: source ${env_file}"
    log_info "3. Run deployment: ./cloudrun/deploy.sh"
    log_info ""
    log_info "Auth token for Lambda configuration: ${auth_token}"
}

# Non-interactive setup from environment variables
non_interactive_setup() {
    local environment=${ENVIRONMENT:-staging}
    local tfvars_file="infra/terraform/gcp/${environment}.tfvars"
    
    log_info "Creating ${tfvars_file} from environment variables..."
    
    cat > "${tfvars_file}" << EOF
# GCP Configuration
gcp_project_id = "${PROJECT_ID}"
gcp_region     = "${REGION:-asia-northeast1}"
environment    = "${environment}"

# AWS Configuration (for DynamoDB access)
aws_access_key_id     = "${AWS_ACCESS_KEY_ID}"
aws_secret_access_key = "${AWS_SECRET_ACCESS_KEY}"
aws_region           = "${AWS_REGION:-ap-northeast-1}"
ddb_table_name       = "${DDB_TABLE_NAME}"

# Authentication
auth_token = "${AUTH_TOKEN}"
EOF
    
    log_info "Configuration file created: ${tfvars_file}"
}

# Main function
main() {
    if [[ "${1:-}" == "--non-interactive" ]]; then
        non_interactive_setup
    else
        interactive_setup
    fi
}

# Run main function
main "$@"
