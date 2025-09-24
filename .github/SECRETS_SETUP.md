# GitHub Secrets 設定

このドキュメントでは、CI/CDパイプラインに必要なGitHub Secretsの設定方法を説明します。

## 必要なSecrets

以下のSecretsをGitHubリポジトリに設定する必要があります：

### AWS認証情報
- `AWS_ACCESS_KEY_ID`: AWSアクセスキーID
- `AWS_SECRET_ACCESS_KEY`: AWSシークレットアクセスキー

### Terraform状態管理
- `TF_STATE_BUCKET`: Terraform状態を保存するS3バケット名
- `TF_STATE_DYNAMODB_TABLE`: Terraform状態ロック用のDynamoDBテーブル名

### アプリケーション設定
- `SENDER_EMAIL_ADDRESS`: SESで使用する送信者メールアドレス
- `SLACK_CHANNEL_ID`: 通知用のSlackチャンネルID

## Secretsの追加方法

1. GitHubリポジトリに移動
2. **Settings** → **Secrets and variables** → **Actions** に移動
3. **New repository secret** をクリック
4. 各Secretに適切な値を追加

## セキュリティのベストプラクティス

### オプション1: 長期アクセスキー（現在の設定）
- 最小限の必要な権限を持つIAMユーザーを使用
- 定期的にキーをローテーション
- AWS CloudTrailで使用状況を監視

### オプション2: OIDC（本番環境推奨）
- GitHub Actions用の信頼ポリシーを持つIAMロールを作成
- アクセスキーの代わりに `role-to-assume` を使用
- 長期認証情報を保存しないため、より安全

## 必要なIAM権限

AWS認証情報には以下の権限が必要です：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-terraform-state-bucket",
                "arn:aws:s3:::your-terraform-state-bucket/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:DeleteItem"
            ],
            "Resource": "arn:aws:dynamodb:region:account:table/your-terraform-state-table"
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:*",
                "apigateway:*",
                "dynamodb:*",
                "sqs:*",
                "ses:*",
                "iam:*",
                "secretsmanager:*",
                "cloudwatch:*"
            ],
            "Resource": "*"
        }
    ]
}
```

## トラブルシューティング

### エラー: "Credentials could not be loaded"
- 必要なSecretsがすべて設定されているか確認
- Secret名が正確に一致しているか確認（大文字小文字を区別）
- AWS認証情報に十分な権限があるか確認

### エラー: "Access Denied"
- IAM権限を確認
- 指定されたリージョンにリソースが存在するか確認
- Terraform状態バケットとテーブルが存在するか確認
