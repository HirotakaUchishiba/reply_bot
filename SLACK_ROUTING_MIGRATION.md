# Slack Request URL Migration Guide

このガイドでは、SlackのRequest URLをAPI GatewayからCloud Runサービスに切り替える手順を説明します。

## 概要

現在の構成:
```
Slack → API Gateway → Lambda
```

新しい構成:
```
Slack → Cloud Run Service → Cloud Run Job (非同期)
```

## 前提条件

1. GCPプロジェクトが作成済み
2. 必要なAPIが有効化済み:
   - Cloud Run API
   - Secret Manager API
   - Artifact Registry API
3. gcloud CLIがインストール・認証済み
4. AWS認証情報（DynamoDBアクセス用）

## デプロイメント手順

### ステップ1: GCPプロジェクトの設定

```bash
# GCPプロジェクトを設定
export GCP_PROJECT_ID="your-actual-gcp-project-id"
gcloud config set project $GCP_PROJECT_ID

# 必要なAPIを有効化
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### ステップ2: GCP Terraformの設定

```bash
cd infra/terraform/gcp

# staging.tfvarsを実際の値で更新
cp staging.tfvars.example staging.tfvars
```

`staging.tfvars`を以下のように更新:
```hcl
# GCP Configuration
gcp_project_id = "your-actual-gcp-project-id"
gcp_region     = "asia-northeast1"
environment    = "staging"

# AWS Configuration (for DynamoDB access)
aws_access_key_id     = "your-actual-aws-access-key-id"
aws_secret_access_key = "your-actual-aws-secret-access-key"
aws_region           = "ap-northeast-1"
ddb_table_name       = "reply-bot-context-staging"

# Authentication
auth_token = "your-secure-auth-token"
```

### ステップ3: GCPインフラのデプロイ

```bash
cd infra/terraform/gcp

# Terraform初期化
terraform init

# プラン確認
terraform plan -var-file=staging.tfvars

# デプロイ実行
terraform apply -var-file=staging.tfvars
```

### ステップ4: Cloud Runサービスのデプロイ

```bash
cd cloudrun

# 環境変数を設定
export PROJECT_ID="your-actual-gcp-project-id"
export REGION="asia-northeast1"
export ENVIRONMENT="staging"
export AWS_ACCESS_KEY_ID="your-actual-aws-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-actual-aws-secret-access-key"
export DDB_TABLE_NAME="reply-bot-context-staging"

# デプロイ実行
./deploy.sh
```

### ステップ5: シークレットの設定

```bash
# Slack Signing Secret
gcloud secrets versions add slack-signing-secret-staging --data-file=<(echo "your-slack-signing-secret")

# Slack Bot Token
gcloud secrets versions add slack-bot-token-staging --data-file=<(echo "your-slack-bot-token")

# OpenAI API Key
gcloud secrets versions add openai-api-key-staging --data-file=<(echo "your-openai-api-key")
```

### ステップ6: AWS側の設定更新

Cloud Runデプロイ後、実際のURLを取得:

```bash
cd infra/terraform/gcp
terraform output cloud_run_service_url
terraform output async_generation_endpoint
```

AWS側の`staging.tfvars`を更新:

```hcl
# Cloud Run async generation configuration
async_generation_endpoint = "https://reply-bot-slack-events-staging-xxxxx-uc.a.run.app/async/generate"
async_generation_auth_header = "Bearer your-secure-auth-token"
```

AWS側のTerraformを適用:

```bash
cd infra/terraform
terraform apply -var-file=staging.tfvars
```

### ステップ7: Slack Appの設定更新

1. [Slack API](https://api.slack.com/apps)にアクセス
2. 対象のアプリを選択
3. "Event Subscriptions" → "Request URL"を更新:
   ```
   https://reply-bot-slack-events-staging-xxxxx-uc.a.run.app/slack/events
   ```
4. "Interactive Components" → "Request URL"も同様に更新
5. 変更を保存

### ステップ8: 動作確認

1. Slackでテストメッセージを送信
2. "返信文を生成する"ボタンをクリック
3. モーダルが即座に開くことを確認
4. 数秒後にAI生成された返信文が表示されることを確認

## ロールバック手順

問題が発生した場合のロールバック:

1. Slack AppのRequest URLを元のAPI Gateway URLに戻す
2. AWS側の`staging.tfvars`で`async_generation_endpoint`を空文字に設定
3. `terraform apply`でAWS側を更新

## 注意事項

- Cloud RunサービスのURLはデプロイ時に自動生成される
- 認証トークンは十分に複雑なものを使用する
- シークレットは適切に管理し、定期的にローテーションする
- デプロイ後は必ず動作確認を行う
