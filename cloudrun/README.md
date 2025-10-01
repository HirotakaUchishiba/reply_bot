# Cloud Run Components for Reply Bot

This directory contains the Cloud Run components for handling Slack events and async reply generation.

## Architecture

1. **Cloud Run Service** (`cloudrun/service/`): Receives Slack events and triggers Cloud Run Jobs
2. **Cloud Run Job** (`cloudrun/job/`): Processes OpenAI generation and updates Slack modals

## Components

### Cloud Run Service
- **Purpose**: Handle Slack events and trigger async processing
- **Endpoints**:
  - `POST /slack/events`: Slack Events API and Interactive Components
  - `POST /async/generate`: Triggered by Lambda for async generation
  - `GET /health`: Health check

### Cloud Run Job
- **Purpose**: Execute OpenAI generation and update Slack modals
- **Triggered by**: Cloud Run Service
- **Process**: Fetch context from DynamoDB → Generate reply → Update Slack modal

## Deployment

### Prerequisites
1. GCP Project with required APIs enabled:
   - Cloud Run API
   - Secret Manager API
   - Artifact Registry API
2. AWS credentials for DynamoDB access
3. Secrets stored in Google Secret Manager

### 1. Deploy Infrastructure
```bash
cd infra/terraform/gcp
cp staging.tfvars.example staging.tfvars
# Edit staging.tfvars with your values

terraform init
terraform plan -var-file=staging.tfvars
terraform apply -var-file=staging.tfvars
```

### 2. Build and Push Docker Images
```bash
# Set variables
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="asia-northeast1"
export REPO_NAME="reply-bot"

# Configure Docker for Artifact Registry
gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev

# Build and push service image
cd cloudrun/service
docker build -t ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/slack-events:latest .
docker push ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/slack-events:latest

# Build and push job image
cd ../job
docker build -t ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/reply-generator:latest .
docker push ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/reply-generator:latest
```

### 3. Update Secrets
```bash
# Set Slack signing secret
gcloud secrets versions add slack-signing-secret-staging --data-file=<(echo -n "your-slack-signing-secret")

# Set Slack bot token
gcloud secrets versions add slack-bot-token-staging --data-file=<(echo -n "xoxb-your-bot-token")

# Set OpenAI API key
gcloud secrets versions add openai-api-key-staging --data-file=<(echo -n "sk-your-openai-key")
```

### 4. Update Lambda Configuration
Update your AWS Lambda environment variables:
```bash
# Get Cloud Run service URL from Terraform output
CLOUD_RUN_URL=$(cd infra/terraform/gcp && terraform output -raw cloud_run_service_url)

# Update Lambda environment variables
aws lambda update-function-configuration \
  --function-name reply-bot-staging \
  --environment Variables='{
    "ASYNC_GENERATION_ENDPOINT": "'${CLOUD_RUN_URL}'/async/generate",
    "ASYNC_GENERATION_AUTH_HEADER": "Bearer your-auth-token"
  }'
```

### 5. Update Slack Request URL
1. Go to Slack App settings
2. Update Request URL to: `{CLOUD_RUN_SERVICE_URL}/slack/events`
3. Save changes

## Environment Variables

### Cloud Run Service
- `GCP_PROJECT_ID`: GCP Project ID
- `GCP_REGION`: GCP Region
- `CLOUD_RUN_JOB_NAME`: Name of the Cloud Run Job
- `SERVICE_ACCOUNT_EMAIL`: Service account email
- `SLACK_SIGNING_SECRET_NAME`: Secret Manager secret name for Slack signing secret
- `STAGE`: Environment stage

### Cloud Run Job
- `GCP_PROJECT_ID`: GCP Project ID
- `GCP_REGION`: GCP Region
- `OPENAI_API_KEY_SECRET_NAME`: Secret Manager secret name for OpenAI API key
- `SLACK_BOT_TOKEN_SECRET_NAME`: Secret Manager secret name for Slack bot token
- `AWS_ACCESS_KEY_ID`: AWS access key for DynamoDB
- `AWS_SECRET_ACCESS_KEY`: AWS secret key for DynamoDB
- `AWS_REGION`: AWS region
- `DDB_TABLE_NAME`: DynamoDB table name

## Testing

### Health Check
```bash
curl https://your-cloud-run-service-url/health
```

### Manual Job Trigger
```bash
curl -X POST https://your-cloud-run-service-url/async/generate \
  -H "Content-Type: application/json" \
  -d '{
    "context_id": "test-context-id",
    "external_id": "ai-reply-test-context-id",
    "stage": "staging"
  }'
```

## Monitoring

- Cloud Run logs: Available in GCP Console
- Cloud Run metrics: CPU, memory, request count, latency
- Secret Manager: Access logs and audit trails
