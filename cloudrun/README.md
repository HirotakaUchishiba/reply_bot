# Reply Bot用Cloud Runコンポーネント

このディレクトリには、Slackイベントの処理と非同期返信生成を行うCloud Runコンポーネントが含まれています。

## アーキテクチャ

1. **Cloud Run Service** (`cloudrun/service/`): Slackイベントを受信し、Cloud Run Jobを起動
2. **Cloud Run Job** (`cloudrun/job/`): OpenAI生成を処理し、Slackモーダルを更新

## コンポーネント

### Cloud Run Service
- **目的**: Slackイベントを処理し、非同期処理をトリガー
- **エンドポイント**:
  - `POST /slack/events`: Slack Events APIとInteractive Components
  - `POST /async/generate`: Lambdaから非同期生成のためにトリガー
  - `GET /health`: ヘルスチェック

### Cloud Run Job
- **目的**: OpenAI生成を実行し、Slackモーダルを更新
- **トリガー**: Cloud Run Service
- **処理**: DynamoDBからコンテキスト取得 → 返信生成 → Slackモーダル更新

## デプロイメント

### 前提条件
1. 必要なAPIが有効化されたGCPプロジェクト:
   - Cloud Run API
   - Secret Manager API
   - Artifact Registry API
2. DynamoDBアクセス用のAWS認証情報
3. Google Secret Managerに保存されたシークレット

### 1. インフラストラクチャのデプロイ
```bash
cd infra/terraform/gcp
cp staging.tfvars.example staging.tfvars
# staging.tfvarsを編集して値を設定

terraform init
terraform plan -var-file=staging.tfvars
terraform apply -var-file=staging.tfvars
```

### 2. Dockerイメージのビルドとプッシュ
```bash
# 変数を設定
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="asia-northeast1"
export REPO_NAME="reply-bot"

# Artifact Registry用にDockerを設定
gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev

# サービスイメージをビルドしてプッシュ
cd cloudrun/service
docker build -t ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/slack-events:latest .
docker push ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/slack-events:latest

# ジョブイメージをビルドしてプッシュ
cd ../job
docker build -t ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/reply-generator:latest .
docker push ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/reply-generator:latest
```

### 3. シークレットの更新
```bash
# Slack署名シークレットを設定
gcloud secrets versions add slack-signing-secret-staging --data-file=<(echo -n "your-slack-signing-secret")

# Slackボットトークンを設定
gcloud secrets versions add slack-bot-token-staging --data-file=<(echo -n "xoxb-your-bot-token")

# OpenAI APIキーを設定
gcloud secrets versions add openai-api-key-staging --data-file=<(echo -n "sk-your-openai-key")
```

### 4. Lambda設定の更新
AWS Lambdaの環境変数を更新:
```bash
# Terraform出力からCloud RunサービスURLを取得
CLOUD_RUN_URL=$(cd infra/terraform/gcp && terraform output -raw cloud_run_service_url)

# Lambda環境変数を更新
aws lambda update-function-configuration \
  --function-name reply-bot-staging \
  --environment Variables='{
    "ASYNC_GENERATION_ENDPOINT": "'${CLOUD_RUN_URL}'/async/generate",
    "ASYNC_GENERATION_AUTH_HEADER": "Bearer your-auth-token"
  }'
```

### 5. Slack Request URLの更新
1. Slack App設定に移動
2. Request URLを以下に更新: `{CLOUD_RUN_SERVICE_URL}/slack/events`
3. 変更を保存

## 環境変数

### Cloud Run Service
- `GCP_PROJECT_ID`: GCPプロジェクトID
- `GCP_REGION`: GCPリージョン
- `CLOUD_RUN_JOB_NAME`: Cloud Run Jobの名前
- `SERVICE_ACCOUNT_EMAIL`: サービスアカウントのメールアドレス
- `SLACK_SIGNING_SECRET_NAME`: Slack署名シークレット用のSecret Managerシークレット名
- `STAGE`: 環境ステージ

### Cloud Run Job
- `GCP_PROJECT_ID`: GCPプロジェクトID
- `GCP_REGION`: GCPリージョン
- `OPENAI_API_KEY_SECRET_NAME`: OpenAI APIキー用のSecret Managerシークレット名
- `SLACK_BOT_TOKEN_SECRET_NAME`: Slackボットトークン用のSecret Managerシークレット名
- `AWS_ACCESS_KEY_ID`: DynamoDB用のAWSアクセスキー
- `AWS_SECRET_ACCESS_KEY`: DynamoDB用のAWSシークレットキー
- `AWS_REGION`: AWSリージョン
- `DDB_TABLE_NAME`: DynamoDBテーブル名

## テスト

### ヘルスチェック
```bash
curl https://your-cloud-run-service-url/health
```

### 手動ジョブトリガー
```bash
curl -X POST https://your-cloud-run-service-url/async/generate \
  -H "Content-Type: application/json" \
  -d '{
    "context_id": "test-context-id",
    "external_id": "ai-reply-test-context-id",
    "stage": "staging"
  }'
```

## 監視

- Cloud Runログ: GCPコンソールで確認可能
- Cloud Runメトリクス: CPU、メモリ、リクエスト数、レイテンシ
- Secret Manager: アクセスログと監査証跡
