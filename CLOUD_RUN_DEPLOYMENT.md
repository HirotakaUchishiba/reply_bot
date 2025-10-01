# Cloud Run Deployment Guide

このガイドでは、Reply BotのCloud Runコンポーネントのデプロイメント手順を説明します。

## アーキテクチャ概要

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Slack App     │───▶│  Cloud Run       │───▶│  Cloud Run      │
│                 │    │  Service         │    │  Job            │
│                 │    │  (Event Handler) │    │  (AI Generator) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Secret Manager  │    │  DynamoDB       │
                       │  (Credentials)   │    │  (Context)      │
                       └──────────────────┘    └─────────────────┘
```

## 前提条件

### 1. GCPプロジェクトの準備
- GCPプロジェクトが作成済み
- 必要なAPIが有効化済み:
  - Cloud Run API
  - Secret Manager API
  - Artifact Registry API
  - Cloud Build API

### 2. 認証情報の準備
- GCP認証: `gcloud auth login`
- AWS認証情報（DynamoDBアクセス用）
- Slack認証情報（Bot Token、Signing Secret）
- OpenAI API Key

### 3. 必要なツール
- `gcloud` CLI
- `docker`
- `terraform`
- `curl`

## デプロイメント手順

### ステップ1: 環境設定

#### 自動設定（推奨）
```bash
cd /path/to/reply_bot
./cloudrun/setup-env.sh
```

#### 手動設定
```bash
# 環境変数を設定
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-northeast1"
export ENVIRONMENT="staging"
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
export DDB_TABLE_NAME="reply-bot-context-staging"
export AUTH_TOKEN="$(openssl rand -hex 32)"

# 設定ファイルを作成
./cloudrun/setup-env.sh --non-interactive
```

### ステップ2: インフラストラクチャのデプロイ

```bash
# デプロイメントスクリプトを実行
./cloudrun/deploy.sh
```

このスクリプトは以下を実行します:
1. 必要なAPIの有効化
2. Docker認証の設定
3. Dockerイメージのビルドとプッシュ
4. Terraformによるインフラストラクチャのデプロイ
5. シークレットの更新

### ステップ3: シークレットの設定

```bash
# Slack署名シークレット
echo -n "your-slack-signing-secret" | gcloud secrets versions add slack-signing-secret-staging --data-file=- --project="${PROJECT_ID}"

# Slackボットトークン
echo -n "xoxb-your-bot-token" | gcloud secrets versions add slack-bot-token-staging --data-file=- --project="${PROJECT_ID}"

# OpenAI APIキー
echo -n "sk-your-openai-key" | gcloud secrets versions add openai-api-key-staging --data-file=- --project="${PROJECT_ID}"
```

### ステップ4: デプロイメントの検証

```bash
# デプロイメントの検証
./cloudrun/validate-deployment.sh
```

### ステップ5: Lambda設定の更新

```bash
# Cloud RunサービスURLを取得
CLOUD_RUN_URL=$(cd infra/terraform/gcp && terraform output -raw cloud_run_service_url)

# Lambda環境変数を更新
aws lambda update-function-configuration \
  --function-name reply-bot-staging \
  --environment Variables='{
    "ASYNC_GENERATION_ENDPOINT": "'${CLOUD_RUN_URL}'/async/generate",
    "ASYNC_GENERATION_AUTH_HEADER": "Bearer '${AUTH_TOKEN}'"
  }'
```

### ステップ6: Slack設定の更新

1. Slack App設定に移動
2. Request URLを以下に更新: `{CLOUD_RUN_SERVICE_URL}/slack/events`
3. 変更を保存

## 設定ファイル

### Terraform変数ファイル (`staging.tfvars`)
```hcl
# GCP Configuration
gcp_project_id = "your-gcp-project-id"
gcp_region     = "asia-northeast1"
environment    = "staging"

# AWS Configuration (for DynamoDB access)
aws_access_key_id     = "your-aws-access-key-id"
aws_secret_access_key = "your-aws-secret-access-key"
aws_region           = "ap-northeast-1"
ddb_table_name       = "reply-bot-context-staging"

# Authentication
auth_token = "your-secure-auth-token"
```

## 環境変数

### Cloud Run Service
- `GCP_PROJECT_ID`: GCPプロジェクトID
- `GCP_REGION`: GCPリージョン
- `CLOUD_RUN_JOB_NAME`: Cloud Run Jobの名前
- `SERVICE_ACCOUNT_EMAIL`: サービスアカウントのメールアドレス
- `SLACK_SIGNING_SECRET_NAME`: Slack署名シークレット用のSecret Managerシークレット名
- `STAGE`: 環境ステージ
- `AUTH_TOKEN`: 認証トークン

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

### 非同期生成エンドポイントのテスト
```bash
curl -X POST https://your-cloud-run-service-url/async/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-auth-token" \
  -d '{
    "context_id": "test-context-id",
    "external_id": "ai-reply-test-context-id",
    "stage": "staging"
  }'
```

### 手動ジョブ実行
```bash
gcloud run jobs execute reply-bot-generator-staging \
  --region=asia-northeast1 \
  --project=your-project-id
```

## トラブルシューティング

### よくある問題

#### 1. デプロイメントが失敗する
```bash
# ログを確認
gcloud run services logs read reply-bot-slack-events-staging --region=asia-northeast1

# Terraformの状態を確認
cd infra/terraform/gcp
terraform plan -var-file=staging.tfvars
```

#### 2. シークレットにアクセスできない
```bash
# シークレットの存在を確認
gcloud secrets list --project=your-project-id

# サービスアカウントの権限を確認
gcloud projects get-iam-policy your-project-id
```

#### 3. Cloud Run Jobが実行されない
```bash
# ジョブの実行履歴を確認
gcloud run jobs executions list --job=reply-bot-generator-staging --region=asia-northeast1

# ジョブのログを確認
gcloud run jobs executions logs --job=reply-bot-generator-staging --region=asia-northeast1
```

### ログの確認

#### Cloud Run Service
```bash
gcloud run services logs read reply-bot-slack-events-staging --region=asia-northeast1 --limit=100
```

#### Cloud Run Job
```bash
gcloud run jobs executions logs --job=reply-bot-generator-staging --region=asia-northeast1
```

## 監視

### Cloud Runメトリクス
- GCPコンソール > Cloud Run > サービス名
- CPU、メモリ、リクエスト数、レイテンシを監視

### ログ監視
- Cloud Loggingでログを検索・フィルタリング
- エラーログのアラート設定

### コスト監視
- Cloud Billingでコストを監視
- Cloud Runの料金は使用量ベース

## セキュリティ

### 推奨事項
1. 最小権限の原則でサービスアカウントを設定
2. シークレットはSecret Managerで管理
3. 認証トークンは定期的にローテーション
4. ネットワークアクセス制限の設定

### セキュリティチェックリスト
- [ ] サービスアカウントの権限が最小限
- [ ] シークレットが適切に管理されている
- [ ] 認証トークンが安全に生成・管理されている
- [ ] ログに機密情報が含まれていない
- [ ] ネットワークアクセスが適切に制限されている

## 更新・メンテナンス

### アプリケーションの更新
```bash
# 新しいイメージをビルド・プッシュ
./cloudrun/deploy.sh

# または個別に更新
cd cloudrun/service
docker build -t asia-northeast1-docker.pkg.dev/your-project/reply-bot/slack-events:latest .
docker push asia-northeast1-docker.pkg.dev/your-project/reply-bot/slack-events:latest
```

### インフラストラクチャの更新
```bash
cd infra/terraform/gcp
terraform plan -var-file=staging.tfvars
terraform apply -var-file=staging.tfvars
```

### シークレットのローテーション
```bash
# 新しいシークレットを追加
echo -n "new-secret-value" | gcloud secrets versions add secret-name --data-file=-

# 古いバージョンを無効化（必要に応じて）
gcloud secrets versions disable 1 --secret=secret-name
```

## 削除

### リソースの削除
```bash
cd infra/terraform/gcp
terraform destroy -var-file=staging.tfvars
```

### 手動削除が必要なリソース
- Artifact Registryのイメージ
- Secret Managerのシークレット（必要に応じて）

## サポート

問題が発生した場合は、以下を確認してください:
1. ログファイル
2. Terraformの状態
3. GCPコンソールでのリソース状態
4. このドキュメントのトラブルシューティングセクション
