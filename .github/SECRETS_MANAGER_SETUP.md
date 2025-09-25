# Secrets Manager設定ガイド

このガイドでは、AWS Secrets Managerに機密情報を設定する手順を説明します。

## 前提条件

- AWS CLIが設定済み
- 適切なIAM権限（Secrets Managerへのアクセス権限）
- 必要な認証情報（OpenAI APIキー、Slack認証情報）

## 設定手順

### 1. OpenAI APIキーの設定

```bash
# ステージング環境
aws secretsmanager put-secret-value \
  --secret-id "reply-bot/stg/openai/api-key" \
  --secret-string "sk-your-openai-api-key-here"

# 本番環境
aws secretsmanager put-secret-value \
  --secret-id "reply-bot/prod/openai/api-key" \
  --secret-string "sk-your-openai-api-key-here"
```

### 2. Slack認証情報の設定

Slackアプリから取得したBot TokenとSigning SecretをJSON形式で設定：

```bash
# ステージング環境
aws secretsmanager put-secret-value \
  --secret-id "reply-bot/stg/slack/app-creds" \
  --secret-string '{"bot_token":"xoxb-your-bot-token","signing_secret":"your-signing-secret"}'

# 本番環境
aws secretsmanager put-secret-value \
  --secret-id "reply-bot/prod/slack/app-creds" \
  --secret-string '{"bot_token":"xoxb-your-bot-token","signing_secret":"your-signing-secret"}'
```

### 3. 設定の確認

```bash
# シークレットの存在確認
aws secretsmanager describe-secret --secret-id "reply-bot/stg/openai/api-key"
aws secretsmanager describe-secret --secret-id "reply-bot/stg/slack/app-creds"

# シークレット値の確認（注意：実際の値は表示されません）
aws secretsmanager get-secret-value --secret-id "reply-bot/stg/openai/api-key"
aws secretsmanager get-secret-value --secret-id "reply-bot/stg/slack/app-creds"
```

## 環境別設定

### ステージング環境
- OpenAI APIキー: `reply-bot/stg/openai/api-key`
- Slack認証情報: `reply-bot/stg/slack/app-creds`

### 本番環境
- OpenAI APIキー: `reply-bot/prod/openai/api-key`
- Slack認証情報: `reply-bot/prod/slack/app-creds`

## セキュリティの考慮事項

### アクセス制御
- IAMロールには最小権限の原則を適用
- 本番環境とステージング環境で異なるシークレットを使用
- 定期的なシークレットのローテーションを検討

### 監査
- CloudTrailでシークレットへのアクセスを監視
- 不正なアクセスパターンを検出するアラートを設定

### バックアップ
- シークレットのバックアップ戦略を検討
- 災害復旧時のシークレット復元手順を準備

## トラブルシューティング

### よくある問題

1. **Access Denied エラー**
   - IAMロールにSecrets Managerへの適切な権限があるか確認
   - シークレットのARNが正しいか確認

2. **シークレットが見つからない**
   - シークレット名が正確か確認
   - 正しいAWSリージョンにいるか確認

3. **JSON形式エラー**
   - Slack認証情報のJSON形式が正しいか確認
   - エスケープ文字が適切に処理されているか確認

## 自動化

### CI/CDパイプラインでの設定

GitHub Actionsでシークレットを設定する場合：

```yaml
- name: Configure Secrets Manager
  run: |
    aws secretsmanager put-secret-value \
      --secret-id "reply-bot/${{ github.ref_name }}/openai/api-key" \
      --secret-string "${{ secrets.OPENAI_API_KEY }}"
    
    aws secretsmanager put-secret-value \
      --secret-id "reply-bot/${{ github.ref_name }}/slack/app-creds" \
      --secret-string '{"bot_token":"${{ secrets.SLACK_BOT_TOKEN }}","signing_secret":"${{ secrets.SLACK_SIGNING_SECRET }}"}'
```

### スクリプト化

設定を自動化するスクリプト例：

```bash
#!/bin/bash
# setup-secrets.sh

ENVIRONMENT=$1
OPENAI_API_KEY=$2
SLACK_BOT_TOKEN=$3
SLACK_SIGNING_SECRET=$4

if [ -z "$ENVIRONMENT" ] || [ -z "$OPENAI_API_KEY" ] || [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_SIGNING_SECRET" ]; then
    echo "Usage: $0 <environment> <openai_api_key> <slack_bot_token> <slack_signing_secret>"
    exit 1
fi

# OpenAI APIキーを設定
aws secretsmanager put-secret-value \
  --secret-id "reply-bot/$ENVIRONMENT/openai/api-key" \
  --secret-string "$OPENAI_API_KEY"

# Slack認証情報を設定
aws secretsmanager put-secret-value \
  --secret-id "reply-bot/$ENVIRONMENT/slack/app-creds" \
  --secret-string "{\"bot_token\":\"$SLACK_BOT_TOKEN\",\"signing_secret\":\"$SLACK_SIGNING_SECRET\"}"

echo "Secrets configured for environment: $ENVIRONMENT"
```

## 参考リンク

- [AWS Secrets Manager User Guide](https://docs.aws.amazon.com/secretsmanager/)
- [AWS CLI Secrets Manager Commands](https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/)
- [IAM Permissions for Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/auth-and-access.html)
