#!/bin/bash
# validate-deployment.sh - Deployment validation script for Reply Bot

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
    echo "  --check-infrastructure  Check AWS infrastructure resources"
    echo "  --check-secrets        Check Secrets Manager configuration"
    echo "  --check-lambda         Check Lambda function status"
    echo "  --check-api-gateway    Check API Gateway configuration"
    echo "  --test-slack-webhook   Test Slack webhook endpoint"
    echo "  --all                  Run all checks (default)"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 staging --all"
    echo "  $0 prod --check-infrastructure"
}

# Function to validate AWS CLI
validate_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured or credentials are invalid."
        exit 1
    fi

    print_success "AWS CLI is configured and working"
}

# Function to validate environment
validate_environment() {
    local env=$1
    if [[ "$env" != "staging" && "$env" != "prod" ]]; then
        print_error "Invalid environment: $env"
        exit 1
    fi
    print_success "Environment validated: $env"
}

# Function to check infrastructure resources
check_infrastructure() {
    local env=$1
    print_status "Checking infrastructure resources for environment: $env"

    # Check Lambda function
    local lambda_name="reply-bot-$env"
    if aws lambda get-function --function-name "$lambda_name" &> /dev/null; then
        print_success "Lambda function exists: $lambda_name"
        
        # Check function configuration
        local config=$(aws lambda get-function-configuration --function-name "$lambda_name")
        local runtime=$(echo "$config" | jq -r '.Runtime')
        local timeout=$(echo "$config" | jq -r '.Timeout')
        local memory=$(echo "$config" | jq -r '.MemorySize')
        
        print_status "  Runtime: $runtime"
        print_status "  Timeout: ${timeout}s"
        print_status "  Memory: ${memory}MB"
    else
        print_error "Lambda function not found: $lambda_name"
        return 1
    fi

    # Check DynamoDB table
    local table_name="reply-bot-context-$env"
    if aws dynamodb describe-table --table-name "$table_name" &> /dev/null; then
        print_success "DynamoDB table exists: $table_name"
    else
        print_error "DynamoDB table not found: $table_name"
        return 1
    fi

    # Check SQS queues
    local dlq_name="reply-bot-dlq-$env"
    if aws sqs get-queue-url --queue-name "$dlq_name" &> /dev/null; then
        print_success "SQS DLQ exists: $dlq_name"
    else
        print_error "SQS DLQ not found: $dlq_name"
        return 1
    fi

    # Check API Gateway
    local api_name="reply-bot-http-$env"
    local api_id=$(aws apigatewayv2 get-apis --query "Items[?Name=='$api_name'].ApiId" --output text)
    if [ -n "$api_id" ] && [ "$api_id" != "None" ]; then
        print_success "API Gateway exists: $api_name (ID: $api_id)"
    else
        print_error "API Gateway not found: $api_name"
        return 1
    fi
}

# Function to check secrets
check_secrets() {
    local env=$1
    print_status "Checking Secrets Manager configuration for environment: $env"

    # Check OpenAI API key secret
    local openai_secret_id="reply-bot/$env/openai/api-key"
    if aws secretsmanager describe-secret --secret-id "$openai_secret_id" &> /dev/null; then
        print_success "OpenAI API key secret exists: $openai_secret_id"
    else
        print_error "OpenAI API key secret not found: $openai_secret_id"
        return 1
    fi

    # Check Slack credentials secret
    local slack_secret_id="reply-bot/$env/slack/app-creds"
    if aws secretsmanager describe-secret --secret-id "$slack_secret_id" &> /dev/null; then
        print_success "Slack credentials secret exists: $slack_secret_id"
    else
        print_error "Slack credentials secret not found: $slack_secret_id"
        return 1
    fi
}

# Function to check Lambda function
check_lambda() {
    local env=$1
    print_status "Checking Lambda function for environment: $env"

    local lambda_name="reply-bot-$env"
    
    # Check function status
    local config=$(aws lambda get-function-configuration --function-name "$lambda_name")
    local state=$(echo "$config" | jq -r '.State')
    local last_modified=$(echo "$config" | jq -r '.LastModified')
    
    print_status "  State: $state"
    print_status "  Last Modified: $last_modified"
    
    if [ "$state" = "Active" ]; then
        print_success "Lambda function is active"
    else
        print_error "Lambda function is not active: $state"
        return 1
    fi

    # Check environment variables
    local env_vars=$(echo "$config" | jq -r '.Environment.Variables')
    print_status "Environment variables:"
    echo "$env_vars" | jq -r 'to_entries[] | "  \(.key): \(.value)"'
}

# Function to check API Gateway
check_api_gateway() {
    local env=$1
    print_status "Checking API Gateway for environment: $env"

    local api_name="reply-bot-http-$env"
    local api_id=$(aws apigatewayv2 get-apis --query "Items[?Name=='$api_name'].ApiId" --output text)
    
    if [ -z "$api_id" ] || [ "$api_id" = "None" ]; then
        print_error "API Gateway not found: $api_name"
        return 1
    fi

    # Get API endpoint
    local api_endpoint=$(aws apigatewayv2 get-api --api-id "$api_id" --query 'ApiEndpoint' --output text)
    print_status "  API Endpoint: $api_endpoint"
    
    # Check routes
    local routes=$(aws apigatewayv2 get-routes --api-id "$api_id" --query 'Items[].RouteKey' --output text)
    print_status "  Routes: $routes"
    
    # Check integrations
    local integrations=$(aws apigatewayv2 get-integrations --api-id "$api_id" --query 'Items[].IntegrationType' --output text)
    print_status "  Integrations: $integrations"
    
    print_success "API Gateway configuration looks good"
    print_status "Slack webhook URL: ${api_endpoint}/slack/events"
}

# Function to test Slack webhook
test_slack_webhook() {
    local env=$1
    print_status "Testing Slack webhook endpoint for environment: $env"

    local api_name="reply-bot-http-$env"
    local api_id=$(aws apigatewayv2 get-apis --query "Items[?Name=='$api_name'].ApiId" --output text)
    
    if [ -z "$api_id" ] || [ "$api_id" = "None" ]; then
        print_error "API Gateway not found: $api_name"
        return 1
    fi

    local api_endpoint=$(aws apigatewayv2 get-api --api-id "$api_id" --query 'ApiEndpoint' --output text)
    local webhook_url="${api_endpoint}/slack/events"
    
    print_status "Testing webhook URL: $webhook_url"
    
    # Test with a simple GET request (should return 405 Method Not Allowed for Slack)
    local response=$(curl -s -o /dev/null -w "%{http_code}" "$webhook_url" || echo "000")
    
    if [ "$response" = "405" ]; then
        print_success "Webhook endpoint is responding (405 Method Not Allowed is expected for GET)"
    elif [ "$response" = "000" ]; then
        print_error "Webhook endpoint is not reachable"
        return 1
    else
        print_warning "Unexpected response code: $response"
    fi
}

# Main function
main() {
    local environment=""
    local check_infrastructure=false
    local check_secrets=false
    local check_lambda=false
    local check_api_gateway=false
    local test_slack_webhook=false
    local run_all=true

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            staging|prod)
                environment="$1"
                shift
                ;;
            --check-infrastructure)
                check_infrastructure=true
                run_all=false
                shift
                ;;
            --check-secrets)
                check_secrets=true
                run_all=false
                shift
                ;;
            --check-lambda)
                check_lambda=true
                run_all=false
                shift
                ;;
            --check-api-gateway)
                check_api_gateway=true
                run_all=false
                shift
                ;;
            --test-slack-webhook)
                test_slack_webhook=true
                run_all=false
                shift
                ;;
            --all)
                run_all=true
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

    print_status "Starting deployment validation for environment: $environment"

    local exit_code=0

    # Run checks based on options
    if [ "$run_all" = "true" ] || [ "$check_infrastructure" = "true" ]; then
        if ! check_infrastructure "$environment"; then
            exit_code=1
        fi
    fi

    if [ "$run_all" = "true" ] || [ "$check_secrets" = "true" ]; then
        if ! check_secrets "$environment"; then
            exit_code=1
        fi
    fi

    if [ "$run_all" = "true" ] || [ "$check_lambda" = "true" ]; then
        if ! check_lambda "$environment"; then
            exit_code=1
        fi
    fi

    if [ "$run_all" = "true" ] || [ "$check_api_gateway" = "true" ]; then
        if ! check_api_gateway "$environment"; then
            exit_code=1
        fi
    fi

    if [ "$run_all" = "true" ] || [ "$test_slack_webhook" = "true" ]; then
        if ! test_slack_webhook "$environment"; then
            exit_code=1
        fi
    fi

    if [ $exit_code -eq 0 ]; then
        print_success "All validation checks passed for environment: $environment"
        print_status "Next steps:"
        echo "  1. Configure Slack app with the webhook URL"
        echo "  2. Set up SES domain authentication"
        echo "  3. Test the complete email workflow"
    else
        print_error "Some validation checks failed for environment: $environment"
        exit 1
    fi
}

# Run main function with all arguments
main "$@"
