# 🚀 Reply Bot デプロイメントチェックリスト

このドキュメントは、Reply Botシステムの完全なデプロイメント手順を提供します。

## 📋 前提条件

### **1. AWS CLI設定**
```bash
# AWS CLIがインストールされていることを確認
aws --version

# AWS認証情報が設定されていることを確認
aws sts get-caller-identity

# リージョンが ap-northeast-1 に設定されていることを確認
aws configure get region
```

### **2. Terraform設定**
```bash
# Terraformがインストールされていることを確認
terraform --version

# 作業ディレクトリに移動
cd infra/terraform
```

### **3. 必要な認証情報**
- [ ] OpenAI APIキー（`sk-proj-`形式）
- [ ] Slack Bot Token（`xoxb-`形式）
- [ ] Slack Signing Secret
- [ ] 送信元メールアドレス
- [ ] SlackチャンネルID

## 🔧 デプロイメント手順

### **ステップ1: Cloud Runデプロイ（非同期生成対応）**
```bash
# Cloud Runコンポーネントをデプロイ
cd infra/terraform/gcp
terraform init
terraform workspace select staging
terraform apply -var-file=staging.tfvars

# デプロイ後のURLを取得
CLOUDRUN_URL=$(terraform output -raw cloud_run_service_url)
echo "Cloud Run URL: $CLOUDRUN_URL"
```

### **ステップ2: AWS Lambda設定の更新**
```bash
# AWS側のTerraformを更新（async_generation_endpointを設定）
cd ../../
terraform init
terraform workspace select staging

# staging.tfvarsにCloud Run URLを設定
# async_generation_endpoint = "https://your-cloudrun-url/async/generate"
# async_generation_auth_header = "Bearer your-auth-token"

terraform apply -var-file=staging.tfvars
```

### **ステップ3: Slack Request URL更新**
```bash
# SlackアプリのRequest URLをCloud Runに更新
./scripts/update-slack-request-url.sh \
  -e staging \
  -u "$CLOUDRUN_URL" \
  -t "your-slack-bot-token"
```

### **ステップ4: 従来のTerraform初期化（参考）**
```bash
cd infra/terraform
terraform init
```

### **ステップ5: ワークスペースの設定**
```bash
# ステージング環境
terraform workspace select staging

# 本番環境（必要に応じて）
terraform workspace select prod
```

### **ステップ6: 設定ファイルの確認**
```bash
# ステージング環境の設定を確認
cat staging.tfvars

# 本番環境の設定を確認
cat prod.tfvars
```

### **ステップ8: インフラの計画確認**
```bash
terraform plan -var-file=staging.tfvars
```

### **ステップ9: インフラのデプロイ**
```bash
terraform apply -var-file=staging.tfvars
```

### **ステップ10: Secrets Managerの設定**
```bash
# スクリプトを使用してSecrets Managerに認証情報を設定
./scripts/setup-secrets.sh staging --interactive
```

### **ステップ11: Slackアプリの設定**
1. [Slack API管理画面](https://api.slack.com/apps)にアクセス
2. 新しいアプリを作成
3. Bot Token Scopesを設定：
   - `chat:write`
   - `chat:write.public`
   - `commands`
4. Interactivity & Shortcutsを有効化
5. Request URLを設定：`https://[CLOUDRUN_URL]/slack/events`（Cloud Runデプロイ後）
6. Event Subscriptionsを有効化
7. アプリをワークスペースにインストール

### **ステップ12: デプロイメントの検証**
```bash
# 検証スクリプトを実行
./scripts/validate-deployment.sh staging
```

## 🧪 テスト手順

### **1. メール送信テスト**
- 設定されたメールアドレスにテストメールを送信
- Slackに通知が届くことを確認

### **2. Slack連携テスト**
- Slackアプリの設定が正しいことを確認
- インタラクティブな要素が動作することを確認

### **3. AI返信生成テスト**
- メール受信から返信生成までのフローをテスト
- PIIレダクションが正常に動作することを確認

## 🔍 トラブルシューティング

### **よくある問題**

#### **1. Lambda関数のインポートエラー**
```bash
# ログを確認
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/reply-bot-staging"
aws logs get-log-events --log-group-name "/aws/lambda/reply-bot-staging" --log-stream-name "[STREAM_NAME]"
```

#### **2. SES認証エラー**
```bash
# 認証済みメールアドレスを確認
aws ses list-verified-email-addresses --region ap-northeast-1
```

#### **3. API Gatewayエラー**
```bash
# API GatewayのURLを確認
terraform output api_gateway_url
```

## 📊 監視とメンテナンス

### **CloudWatchダッシュボード**
- Lambda関数の実行状況
- DynamoDBの読み書き状況
- API Gatewayのリクエスト数

### **アラーム設定**
- Lambda関数のエラー率
- DynamoDBの読み書き容量
- API Gatewayの4xx/5xxエラー率

## 🔒 セキュリティ考慮事項

### **1. Secrets Manager**
- すべての機密情報はSecrets Managerに保存
- 適切なIAM権限を設定

### **2. PII保護**
- Microsoft Presidioを使用したPIIレダクション
- レダクションされたデータの安全な保存

### **3. ネットワークセキュリティ**
- VPCエンドポイントの使用（必要に応じて）
- 適切なセキュリティグループの設定

## 📝 ログと監査

### **ログの場所**
- Lambda関数ログ：`/aws/lambda/reply-bot-[environment]`
- API Gatewayログ：`/aws/apigateway/[api-id]`
- DynamoDBログ：CloudTrail

### **ログの保持期間**
- CloudWatch Logs：30日間
- CloudTrail：90日間

## 🚨 緊急時の対応

### **システムダウンの場合**
1. CloudWatchダッシュボードで状況確認
2. Lambda関数のログを確認
3. 必要に応じてロールバック

### **データ復旧**
- DynamoDBのポイントインタイムリカバリを使用
- バックアップからの復旧手順を確認

## 📞 サポート

問題が発生した場合は、以下の情報を収集してください：
- エラーメッセージ
- CloudWatchログ
- 発生時刻
- 実行していた操作

---

**最終更新**: 2025年9月26日
**バージョン**: 1.0.0