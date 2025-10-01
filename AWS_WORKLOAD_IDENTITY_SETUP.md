# AWS Workload Identity Setup Guide

このドキュメントでは、Cloud Run JobワーカーからAWS DynamoDBにアクセスするためのWorkload Identity連携の設定手順を説明します。

## 概要

従来のAWS Access Key ID/Secret Access Keyによる認証から、より安全なWorkload Identity連携による認証に変更しました。

### 変更点

- **従来**: AWS Access Key ID/Secret Access Keyを環境変数で直接設定
- **新方式**: GCP Service AccountとAWS IAMロールをWorkload Identityで連携

## 設定手順

### 1. AWS側の設定

#### 1.1 OIDC Identity Providerの作成

```bash
# AWS CLIでOIDC Identity Providerを作成
aws iam create-open-id-connect-provider \
  --url https://accounts.google.com \
  --thumbprint-list 8b5a0c6c2c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c \
  --client-id-list "your-gcp-project-id.apps.googleusercontent.com"
```

#### 1.2 AWS IAMロールとポリシーの作成

```bash
# TerraformでAWSリソースを作成
cd infra/terraform/gcp
terraform apply -target=aws_iam_role.cloudrun_workload_identity
terraform apply -target=aws_iam_policy.cloudrun_dynamodb_access
terraform apply -target=aws_iam_role_policy_attachment.cloudrun_dynamodb_policy
```

### 2. GCP側の設定

#### 2.1 Workload Identity Poolの作成

```bash
# GCP側のTerraformを適用
cd infra/terraform/gcp
terraform apply
```

#### 2.2 必要な変数の設定

`staging.tfvars`に以下の値を設定：

```hcl
# AWS Configuration
aws_account_id                    = "123456789012"  # あなたのAWSアカウントID
aws_workload_identity_role_arn    = "arn:aws:iam::123456789012:role/reply-bot-cloudrun-workload-identity-staging"
aws_oidc_provider_id              = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 上記で作成したOIDC Provider ID
aws_region                        = "ap-northeast-1"
ddb_table_name                    = "reply-bot-context-staging"
```

### 3. デプロイメント

#### 3.1 Cloud Runサービスのデプロイ

```bash
# コンテナイメージのビルドとプッシュ
cd cloudrun
./build-and-push.sh

# Cloud Runサービスのデプロイ
gcloud run deploy reply-bot-slack-events-staging \
  --image asia-northeast1-docker.pkg.dev/your-project/reply-bot/slack-events:latest \
  --region asia-northeast1 \
  --service-account reply-bot-cloudrun-staging@your-project.iam.gserviceaccount.com
```

#### 3.2 Cloud Run Jobのデプロイ

```bash
# Cloud Run Jobのデプロイ
gcloud run jobs replace job-config.yaml
```

## 認証フロー

1. **Cloud Run Job起動**: GCP Service Accountで認証
2. **OIDC Token取得**: Google CloudからOIDCトークンを取得
3. **AWS STS呼び出し**: OIDCトークンを使用してAWS STSのAssumeRoleWithWebIdentityを呼び出し
4. **一時認証情報取得**: AWSから一時的な認証情報（Access Key, Secret Key, Session Token）を取得
5. **DynamoDBアクセス**: 一時認証情報を使用してDynamoDBにアクセス

## セキュリティ上の利点

- **長期認証情報の排除**: AWS Access Key ID/Secret Access Keyを環境変数で管理する必要がない
- **最小権限の原則**: DynamoDBへの読み取り権限のみを付与
- **監査可能性**: すべてのアクセスがCloudTrailで記録される
- **自動ローテーション**: 一時認証情報は自動的に期限切れになる

## トラブルシューティング

### よくある問題

1. **OIDC Provider IDが間違っている**
   - AWS IAMコンソールでOIDC Identity ProviderのIDを確認

2. **IAMロールの信頼ポリシーが正しくない**
   - `aws_iam_role.cloudrun_workload_identity`のassume_role_policyを確認

3. **GCP Service Accountの権限不足**
   - `roles/iam.workloadIdentityUser`が正しく付与されているか確認

### ログの確認

```bash
# Cloud Run Jobのログを確認
gcloud logging read "resource.type=cloud_run_job" --limit=50

# AWS CloudTrailでAssumeRoleWithWebIdentityの呼び出しを確認
aws logs filter-log-events \
  --log-group-name CloudTrail \
  --filter-pattern "AssumeRoleWithWebIdentity"
```

## 参考資料

- [AWS IAM Identity Providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [Google Cloud Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
- [AWS STS AssumeRoleWithWebIdentity](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
