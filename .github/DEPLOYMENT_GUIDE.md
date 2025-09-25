# デプロイメントガイド

このガイドでは、Slack AI Email Assistantを異なる環境にデプロイする方法を説明します。

## 前提条件

1. **GitHub Secrets設定**
   - [SECRETS_SETUP.md](./SECRETS_SETUP.md)の指示に従ってください
   - 必要なSecretsがすべて設定されていることを確認してください

2. **AWSリソース**
   - Terraform状態用S3バケット
   - Terraform状態用DynamoDBテーブル
   - 適切なIAM権限

3. **設定ファイルの準備**
   - `infra/terraform/staging.tfvars` - ステージング環境設定
   - `infra/terraform/prod.tfvars` - 本番環境設定
   - `infra/terraform/backend.auto.tfvars` - バックエンド設定

4. **外部サービス設定**
   - Slackアプリの作成と設定
   - SES送信ドメインの認証（SPF/DKIM/DMARC）
   - OpenAI APIキーの取得

## デプロイメント環境

### ステージング環境
- **トリガー**: `develop`ブランチへのプッシュ
- **環境**: `staging`
- **URL**: `https://{api_gateway_id}.execute-api.ap-northeast-1.amazonaws.com/slack/events`
- **保護**: 1人のレビュアーが必要

### 本番環境
- **トリガー**: `main`ブランチへのプッシュ
- **環境**: `production`
- **URL**: `https://{api_gateway_id}.execute-api.ap-northeast-1.amazonaws.com/slack/events`
- **保護**: 2人のレビュアーが必要、5分間の待機タイマー

## デプロイメントプロセス

### 自動デプロイメント
1. **コード変更**: `develop`または`main`ブランチにプッシュ
2. **CIパイプライン**: テストが自動実行
3. **Terraform Plan**: インフラ変更が計画される
4. **手動承認**: 本番デプロイメントには必要
5. **デプロイメント**: Terraformでインフラがデプロイされる

### 手動デプロイメント
手動でデプロイメントをトリガーする場合：

1. GitHubの**Actions**タブに移動
2. **Deploy Slack AI Email Assistant**ワークフローを選択
3. **Run workflow**をクリック
4. ブランチと環境を選択
5. **Run workflow**をクリック

## デプロイ後の設定

### 1. API Gateway URLの取得
デプロイ完了後、Terraformの出力からAPI Gateway URLを取得：
```bash
cd infra/terraform
terraform output api_gateway_url
```

### 2. Slackアプリの設定更新
1. Slack APIの管理画面にアクセス
2. アプリの設定 > Interactivity & Shortcuts
3. Request URLを上記で取得したURLに更新
4. 変更を保存

### 3. Secrets Managerへの値設定
以下のSecretsに実際の値を設定：
- `reply-bot/{env}/openai/api-key` - OpenAI APIキー
- `reply-bot/{env}/slack/app-creds` - Slack Bot TokenとSigning Secret
- 詳細手順: [SECRETS_MANAGER_SETUP.md](./SECRETS_MANAGER_SETUP.md)

### 4. SES送信ドメインの認証
- SPFレコードの設定
- DKIM認証の設定
- DMARCポリシーの設定（最低p=none）
- 詳細手順: [SES_DOMAIN_SETUP.md](./SES_DOMAIN_SETUP.md)

## デプロイメントの監視

### GitHub Actions
- **Actions**タブでデプロイメント状況を監視
- エラーや警告のログを確認
- Terraform planの出力を確認

### AWS Console
- リソースが正しく作成されているか確認
- Lambda関数のログを確認
- API Gatewayエンドポイントを監視
- CloudWatchダッシュボードでメトリクスを確認

## トラブルシューティング

### よくある問題

1. **Secretsが設定されていない**
   - エラー: "Credentials could not be loaded"
   - 解決策: SECRETS_SETUP.mdに従ってGitHub Secretsを設定

2. **Terraform状態の問題**
   - エラー: "Failed to load state"
   - 解決策: S3バケットとDynamoDBテーブルが存在することを確認

3. **権限拒否**
   - エラー: "Access Denied"
   - 解決策: AWS認証情報のIAM権限を確認

### ロールバックプロセス
デプロイメントが失敗した場合や問題が発生した場合：

1. **即座に**: AWS ConsoleでLambda関数を無効化
2. **調査**: ログを確認して問題を特定
3. **修正**: 新しいブランチで修正を適用
4. **再デプロイ**: 修正されたバージョンをデプロイ

## 環境変数

各環境には特定の設定があります：

| 変数 | ステージング | 本番 |
|------|-------------|------|
| AWS_REGION | ap-northeast-1 | ap-northeast-1 |
| ENVIRONMENT | staging | production |
| LOG_LEVEL | DEBUG | INFO |

## セキュリティの考慮事項

1. **Secrets管理**: コードにSecretsをコミットしない
2. **アクセス制御**: IAMロールには最小権限の原則を使用
3. **監視**: 監査ログのためにCloudTrailを有効化
4. **更新**: 依存関係とセキュリティパッチを定期的に更新
