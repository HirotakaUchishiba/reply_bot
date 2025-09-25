#!/bin/bash
# setup-secrets.sh - Secrets Manager setup script for Reply Bot

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 <environment> [options]"
    echo ""
    echo "Environment: staging | prod"
    echo ""
    echo "Options:"
    echo "  --openai-key <key>     OpenAI API key"
    echo "  --slack-bot-token <token>  Slack Bot Token"
    echo "  --slack-signing-secret <secret>  Slack Signing Secret"
    echo "  --interactive          Interactive mode (prompts for values)"
    echo "  --dry-run             Show what would be done without executing"
    echo "  --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 staging --interactive"
    echo "  $0 prod --openai-key sk-xxx --slack-bot-token xoxb-xxx --slack-signing-secret xxx"
}

# Function to validate AWS CLI
validate_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured or credentials are invalid."
        print_error "Please run 'aws configure' to set up your credentials."
        exit 1
    fi

    print_success "AWS CLI is configured and working"
}

# Function to validate environment
validate_environment() {
    local env=$1
    if [[ "$env" != "staging" && "$env" != "prod" ]]; then
        print_error "Invalid environment: $env"
        print_error "Environment must be 'staging' or 'prod'"
        exit 1
    fi
    print_success "Environment validated: $env"
}

# Function to check if secret exists
secret_exists() {
    local secret_id=$1
    aws secretsmanager describe-secret --secret-id "$secret_id" &> /dev/null
}

# Function to create or update secret
create_or_update_secret() {
    local secret_id=$1
    local secret_value=$2
    local description=$3
    local dry_run=$4

    if [ "$dry_run" = "true" ]; then
        print_status "DRY RUN: Would set secret '$secret_id'"
        return 0
    fi

    if secret_exists "$secret_id"; then
        print_status "Updating existing secret: $secret_id"
        aws secretsmanager put-secret-value \
            --secret-id "$secret_id" \
            --secret-string "$secret_value" \
            --output table
    else
        print_status "Creating new secret: $secret_id"
        aws secretsmanager create-secret \
            --name "$secret_id" \
            --description "$description" \
            --secret-string "$secret_value" \
            --output table
    fi
    print_success "Secret configured: $secret_id"
}

# Function to get user input
get_user_input() {
    local prompt=$1
    local var_name=$2
    local is_secret=${3:-false}
    
    if [ "$is_secret" = "true" ]; then
        read -s -p "$prompt: " "$var_name"
        echo
    else
        read -p "$prompt: " "$var_name"
    fi
}

# Main function
main() {
    local environment=""
    local openai_key=""
    local slack_bot_token=""
    local slack_signing_secret=""
    local interactive=false
    local dry_run=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            staging|prod)
                environment="$1"
                shift
                ;;
            --openai-key)
                openai_key="$2"
                shift 2
                ;;
            --slack-bot-token)
                slack_bot_token="$2"
                shift 2
                ;;
            --slack-signing-secret)
                slack_signing_secret="$2"
                shift 2
                ;;
            --interactive)
                interactive=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Validate required arguments
    if [ -z "$environment" ]; then
        print_error "Environment is required"
        show_usage
        exit 1
    fi

    # Validate AWS CLI
    validate_aws_cli

    # Validate environment
    validate_environment "$environment"

    print_status "Setting up secrets for environment: $environment"

    # Interactive mode
    if [ "$interactive" = "true" ]; then
        if [ -z "$openai_key" ]; then
            get_user_input "Enter OpenAI API key" "openai_key" true
        fi
        if [ -z "$slack_bot_token" ]; then
            get_user_input "Enter Slack Bot Token (xoxb-...)" "slack_bot_token" true
        fi
        if [ -z "$slack_signing_secret" ]; then
            get_user_input "Enter Slack Signing Secret" "slack_signing_secret" true
        fi
    fi

    # Validate required values
    if [ -z "$openai_key" ] || [ -z "$slack_bot_token" ] || [ -z "$slack_signing_secret" ]; then
        print_error "All secrets are required. Use --interactive mode or provide all values via command line."
        show_usage
        exit 1
    fi

    # Validate OpenAI key format
    if [[ ! "$openai_key" =~ ^sk- ]]; then
        print_warning "OpenAI API key should start with 'sk-'"
    fi

    # Validate Slack bot token format
    if [[ ! "$slack_bot_token" =~ ^xoxb- ]]; then
        print_warning "Slack Bot Token should start with 'xoxb-'"
    fi

    # Set up secrets
    local openai_secret_id="reply-bot/$environment/openai/api-key"
    local slack_secret_id="reply-bot/$environment/slack/app-creds"

    # Create OpenAI API key secret
    create_or_update_secret \
        "$openai_secret_id" \
        "$openai_key" \
        "OpenAI API key for Reply Bot $environment environment" \
        "$dry_run"

    # Create Slack credentials secret
    local slack_credentials="{\"bot_token\":\"$slack_bot_token\",\"signing_secret\":\"$slack_signing_secret\"}"
    create_or_update_secret \
        "$slack_secret_id" \
        "$slack_credentials" \
        "Slack app credentials for Reply Bot $environment environment" \
        "$dry_run"

    if [ "$dry_run" = "true" ]; then
        print_warning "Dry run completed. No secrets were actually created or updated."
    else
        print_success "All secrets have been configured for environment: $environment"
        print_status "Next steps:"
        echo "  1. Deploy the infrastructure using Terraform"
        echo "  2. Configure Slack app with the API Gateway URL"
        echo "  3. Set up SES domain authentication"
        echo "  4. Test the complete workflow"
    fi
}

# Run main function with all arguments
main "$@"
