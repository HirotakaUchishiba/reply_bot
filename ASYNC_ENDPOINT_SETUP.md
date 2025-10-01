# 非同期生成エンドポイント設定ガイド

このガイドでは、Cloud Runデプロイ後に`async_generation_endpoint`と`async_generation_auth_header`を設定する手順を説明します。

## 前提条件

- Cloud Runサービスがデプロイ済み
- GCPプロジェクトでTerraformが実行済み
- AWS Lambda側のTerraformが実行可能

## 設定手順

### ステップ1: Cloud Run URLの取得

```bash
# GCP Terraformディレクトリに移動
cd infra/terraform/gcp

# Cloud RunサービスのURLを取得
CLOUDRUN_URL=$(terraform output -raw cloud_run_service_url)
echo "Cloud Run URL: $CLOUDRUN_URL"

# 非同期生成エンドポイントのURLを構築
ASYNC_ENDPOINT="${CLOUDRUN_URL}/async/generate"
echo "Async Endpoint: $ASYNC_ENDPOINT"
```

### ステップ2: 認証トークンの取得

```bash
# GCP Secret Managerから認証トークンを取得
AUTH_TOKEN=$(gcloud secrets versions access latest --secret="reply-bot-auth-token-staging")
echo "Auth Token: $AUTH_TOKEN"
```

### ステップ3: AWS Lambda設定の更新

```bash
# AWS Terraformディレクトリに移動
cd ../../

# staging.tfvarsを編集
cat > staging.tfvars << EOF
aws_region = "ap-northeast-1"

# Terraform state configuration
tf_state_bucket         = "reply-bot-terraform-state-20241224"
tf_state_key_prefix     = "reply-bot"
tf_state_dynamodb_table = "reply-bot-terraform-state-lock"

# DynamoDB configuration
ddb_table_name      = "reply-bot-context-staging"
ddb_ttl_attribute   = "ttl_epoch"

# Secrets Manager configuration
secret_name_openai_api_key = "reply-bot/stg/openai/api-key"
secret_name_slack_app      = "reply-bot/stg/slack/app-creds"

# SES configuration
ses_rule_set_name = "reply-bot-rule-set"
ses_recipients    = ["hirotaka19990821@gmail.com"]

# Application configuration
sender_email_address = "hirotaka19990821@gmail.com"
slack_channel_id     = "C09H7V2BFNG"

# Monitoring configuration
alarm_lambda_error_threshold = 1
alarm_apigw_5xx_threshold    = 1

# Cloud Run async generation configuration
async_generation_endpoint = "${ASYNC_ENDPOINT}"
async_generation_auth_header = "Bearer ${AUTH_TOKEN}"
EOF

# Terraform applyを実行
terraform apply -var-file=staging.tfvars
```

### ステップ4: Slack Request URLの更新

```bash
# Slack Bot Tokenを取得（Secrets Managerから）
SLACK_BOT_TOKEN=$(aws secretsmanager get-secret-value \
  --secret-id "reply-bot/stg/slack/app-creds" \
  --query 'SecretString' --output text | jq -r '.bot_token')

# Slack Request URLを更新
./scripts/update-slack-request-url.sh \
  -e staging \
  -u "$CLOUDRUN_URL" \
  -t "$SLACK_BOT_TOKEN"
```

### ステップ5: 動作確認

```bash
# デプロイメント検証スクリプトを実行
./scripts/validate-deployment.sh staging

# Cloud Runサービスのヘルスチェック
curl -f "${CLOUDRUN_URL}/health" || echo "Health check failed"

# 非同期生成エンドポイントのテスト
curl -X POST "${ASYNC_ENDPOINT}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"context_id": "test", "external_id": "test-modal", "stage": "staging"}' \
  -v
```

## トラブルシューティング

### よくある問題

1. **Cloud Run URLが取得できない**
   ```bash
   # GCPプロジェクトが正しく設定されているか確認
   gcloud config get-value project
   
   # Terraformの状態を確認
   cd infra/terraform/gcp
   terraform show
   ```

2. **認証トークンが取得できない**
   ```bash
   # Secret Managerのシークレット一覧を確認
   gcloud secrets list --filter="name:reply-bot"
   
   # シークレットの詳細を確認
   gcloud secrets describe reply-bot-auth-token-staging
   ```

3. **Slack Request URL更新が失敗する**
   ```bash
   # Slack Bot Tokenが正しいか確認
   curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
     "https://slack.com/api/auth.test"
   
   # アプリのマニフェストを確認
   curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
     "https://slack.com/api/apps.manifest.get" | jq '.'
   ```

### ログの確認

```bash
# Cloud Runサービスのログを確認
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=reply-bot-slack-events-staging" --limit=50

# AWS Lambdaのログを確認
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/reply-bot-staging"
```

## 設定値の確認

設定が正しく反映されているか確認するには：

```bash
# AWS Lambdaの環境変数を確認
aws lambda get-function-configuration \
  --function-name reply-bot-staging \
  --query 'Environment.Variables.{ASYNC_GENERATION_ENDPOINT:ASYNC_GENERATION_ENDPOINT,ASYNC_GENERATION_AUTH_HEADER:ASYNC_GENERATION_AUTH_HEADER}'

# Cloud Runサービスの環境変数を確認
gcloud run services describe reply-bot-slack-events-staging \
  --region=asia-northeast1 \
  --format="value(spec.template.spec.template.spec.containers[0].env[].name,spec.template.spec.template.spec.containers[0].env[].value)"
```

## 次のステップ

設定完了後は以下を実行してください：

1. **E2Eテスト**: 実際のSlackボタンクリックで非同期生成が動作するか確認
2. **モニタリング**: CloudWatchとGCP Loggingでエラーがないか確認
3. **パフォーマンス**: 生成時間とレスポンス時間を測定
4. **本番環境**: 同様の手順で本番環境にも適用
