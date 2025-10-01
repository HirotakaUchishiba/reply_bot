# 非同期Slackワークフロー ドキュメント

## 概要

このドキュメントでは、Slack Botの非同期返信生成ワークフローの実装と運用について説明します。従来の同期処理から、Cloud Runを活用した非同期処理への移行により、Slack APIの3秒タイムアウト制限を回避し、より高品質なAI返信生成を実現します。

## アーキテクチャ

### 従来の同期ワークフロー
```
Slack Button Click → Lambda (3秒以内) → OpenAI API → Modal表示
```

### 新しい非同期ワークフロー
```
Slack Button Click → Lambda (即座) → Modal表示
                   ↓
                Cloud Run Service → Cloud Run Job → OpenAI API → Modal更新
```

## コンポーネント

### 1. AWS Lambda (既存)
- **役割**: Slackイベントの即座処理、モーダル表示
- **変更点**: 
  - 非同期エンドポイントが設定されている場合、即座にモーダルを表示
  - Cloud Runサービスに非同期生成をトリガー
- **設定**: `ASYNC_GENERATION_ENDPOINT`、`ASYNC_GENERATION_AUTH_HEADER`

### 2. Cloud Run Service
- **役割**: Slackイベント受信、Cloud Run Job起動
- **エンドポイント**:
  - `POST /async/generate`: 非同期生成トリガー
  - `POST /slack/events`: Slackイベント処理
  - `GET /health`: ヘルスチェック

### 3. Cloud Run Job
- **役割**: OpenAI API呼び出し、Slackモーダル更新
- **処理フロー**:
  1. DynamoDBからコンテキスト取得
  2. OpenAI APIで返信生成
  3. PII復元
  4. Slackモーダル更新

## 設定

### 環境変数

#### AWS Lambda
```bash
ASYNC_GENERATION_ENDPOINT=https://your-cloudrun-service.run.app/async/generate
ASYNC_GENERATION_AUTH_HEADER=Bearer your-auth-token
```

#### Cloud Run Service
```bash
SLACK_SIGNING_SECRET_NAME=projects/your-project/secrets/slack-signing-secret/versions/latest
SLACK_BOT_TOKEN_NAME=projects/your-project/secrets/slack-bot-token/versions/latest
CLOUD_RUN_JOB_NAME=reply-bot-worker
CLOUD_RUN_JOB_REGION=asia-northeast1
```

#### Cloud Run Job
```bash
OPENAI_API_KEY=your-openai-api-key
SLACK_BOT_TOKEN=xoxb-your-bot-token
DDB_TABLE_NAME=reply-bot-context-staging
```

### Terraform設定

#### staging.tfvars
```hcl
async_generation_endpoint = "https://your-cloudrun-service.run.app/async/generate"
async_generation_auth_header = "Bearer your-auth-token"
```

## デプロイ手順

### 1. Cloud Runリソースのデプロイ
```bash
cd cloudrun
./deploy.sh staging
```

### 2. AWS Lambdaの更新
```bash
cd infra/terraform
terraform apply -var-file=staging.tfvars
```

### 3. Slack Request URLの更新
```bash
./scripts/update-slack-request-url.sh
```

### 4. 動作確認
```bash
./cloudrun/validate-deployment.sh
```

## テスト

### ユニットテスト
```bash
# Lambda側のテスト
pytest tests/test_async_slack_workflow.py -v

# 設定のテスト
pytest tests/test_async_config.py -v

# Cloud Run統合テスト
pytest tests/test_cloudrun_integration.py -v
```

### E2Eテスト
```bash
# 非同期ワークフローのE2Eテスト
pytest tests/test_async_slack_workflow.py::TestAsyncSlackWorkflow::test_async_generation_workflow_with_endpoint -v
```

## トラブルシューティング

### よくある問題

#### 1. モーダルが更新されない
- **原因**: `external_id`が正しく設定されていない
- **解決**: Lambda側で`external_id`の生成を確認

#### 2. 非同期エンドポイントが呼ばれない
- **原因**: `ASYNC_GENERATION_ENDPOINT`が設定されていない
- **解決**: 環境変数の設定を確認

#### 3. Cloud Run Jobが失敗する
- **原因**: 認証情報や権限の問題
- **解決**: GCP Workload Identityの設定を確認

### ログ確認

#### AWS Lambda
```bash
aws logs tail /aws/lambda/reply-bot-staging --follow
```

#### Cloud Run Service
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=reply-bot-service" --limit=50
```

#### Cloud Run Job
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=reply-bot-worker" --limit=50
```

## パフォーマンス

### レスポンス時間
- **モーダル表示**: < 1秒
- **AI生成完了**: 5-15秒（OpenAI API依存）
- **モーダル更新**: < 1秒

### スケーラビリティ
- **Cloud Run Service**: 自動スケーリング（0-1000インスタンス）
- **Cloud Run Job**: 並列実行可能
- **AWS Lambda**: 既存の制限内

## セキュリティ

### 認証・認可
- **Slack**: 署名検証
- **Cloud Run**: IAM認証
- **AWS**: Workload Identity

### データ保護
- **PII**: 自動マスキング・復元
- **Secrets**: GCP Secret Manager
- **通信**: HTTPS/TLS

## 監視・アラート

### メトリクス
- **Cloud Run Service**: リクエスト数、エラー率、レイテンシ
- **Cloud Run Job**: 実行時間、成功率
- **AWS Lambda**: 呼び出し数、エラー率

### アラート
- **エラー率 > 5%**: 即座に通知
- **レイテンシ > 30秒**: 警告通知
- **Job失敗**: 即座に通知

## 移行ガイド

### 段階的移行
1. **Phase 1**: 非同期エンドポイント未設定（従来動作）
2. **Phase 2**: 非同期エンドポイント設定（新動作）
3. **Phase 3**: Slack Request URL切替

### ロールバック
```bash
# Slack Request URLを元に戻す
./scripts/update-slack-request-url.sh --rollback

# 非同期エンドポイントを無効化
terraform apply -var='async_generation_endpoint=""' -var-file=staging.tfvars
```

## 今後の改善

### 機能拡張
- [ ] 複数言語対応
- [ ] カスタムプロンプト
- [ ] 生成履歴管理
- [ ] バッチ処理対応

### パフォーマンス改善
- [ ] キャッシュ機能
- [ ] ストリーミング生成
- [ ] 並列処理最適化

### 運用改善
- [ ] 自動スケーリング調整
- [ ] コスト最適化
- [ ] 監視ダッシュボード
