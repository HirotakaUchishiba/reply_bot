# TerraformでAWS設定値を確認する方法 - 実践ガイド

## はじめに

TerraformでAWSリソースを管理する際、`aws_account_id`や`aws_oidc_provider_id`などの値を手動で入力する必要があることがあります。この記事では、これらの値を効率的に確認する方法を実践的に解説します。

## 1. AWS Account IDの確認方法

### 1.1 AWS CLIを使用した確認

最も簡単で確実な方法は、AWS CLIを使用することです：

```bash
aws sts get-caller-identity --query Account --output text
```

このコマンドは現在のAWS認証情報に基づいてアカウントIDを返します。

### 1.2 詳細情報の取得

より詳細な情報が必要な場合：

```bash
aws sts get-caller-identity
```

出力例：
```json
{
    "UserId": "AIDACKCEVSQ6C2EXAMPLE",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/username"
}
```

### 1.3 その他の確認方法

- **AWS Management Console**: 右上のアカウント名をクリック
- **IAM ロールのARN**: 既存のIAMロールのARNから抽出（例：`arn:aws:iam::123456789012:role/...`）

## 2. AWS OIDC Provider IDの確認方法

### 2.1 既存のOIDC Providerの確認

```bash
aws iam list-open-id-connect-providers --output json
```

### 2.2 特定のプロバイダーの検索

Google Cloud連携用のプロバイダーを検索：

```bash
aws iam list-open-id-connect-providers \
  --query 'OpenIDConnectProviderList[?contains(Arn, `gcp`) || contains(Arn, `google`)].{Arn:Arn,ProviderId:ProviderId}' \
  --output table
```

### 2.3 OIDC Providerが存在しない場合の作成

Workload Identity連携でGoogle CloudとAWSを連携する場合、OIDC Identity Providerを作成する必要があります：

```bash
aws iam create-open-id-connect-provider \
  --url https://accounts.google.com \
  --thumbprint-list 8b5a0c6c2c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c \
  --client-id-list "your-gcp-project-id.apps.googleusercontent.com"
```

作成後、Provider IDは通常URLのホスト名部分（`accounts.google.com`）になります。

## 3. AWS IAM Role ARNの確認方法

### 3.1 特定のロール名で検索

```bash
aws iam list-roles \
  --query 'Roles[?contains(RoleName, `workload-identity`)].{RoleName:RoleName,Arn:Arn}' \
  --output table
```

### 3.2 プロジェクト関連のロールを検索

```bash
aws iam list-roles \
  --query 'Roles[?contains(RoleName, `your-project-name`)].{RoleName:RoleName,Arn:Arn}' \
  --output table
```

### 3.3 ロールが存在しない場合

Terraformで管理されるロールの場合、期待されるARNは以下の形式になります：

```
arn:aws:iam::YOUR_ACCOUNT_ID:role/ROLE_NAME
```

例：
```
arn:aws:iam::123456789012:role/your-project-workload-identity-staging
```

## 4. Terraformでの実践的な使い方

### 4.1 変数ファイルの設定

`terraform.tfvars`または`staging.tfvars`に設定：

```hcl
# AWS Configuration
aws_account_id                    = "123456789012"  # aws sts get-caller-identityで確認
aws_oidc_provider_id              = "accounts.google.com"  # 作成したOIDC ProviderのID
aws_workload_identity_role_arn    = "arn:aws:iam::123456789012:role/your-project-workload-identity-staging"
aws_region                        = "ap-northeast-1"
```

### 4.2 動的な値の取得

Terraformで動的に値を取得する場合：

```hcl
data "aws_caller_identity" "current" {}

locals {
  aws_account_id = data.aws_caller_identity.current.account_id
}
```

## 5. トラブルシューティング

### 5.1 よくある問題

1. **権限不足**: AWS CLIの認証情報に必要な権限がない
2. **リージョンの違い**: 異なるリージョンにリソースが存在する
3. **リソースの不存在**: 参照しようとしているリソースがまだ作成されていない

### 5.2 デバッグコマンド

```bash
# 現在の認証情報を確認
aws sts get-caller-identity

# 利用可能なリージョンを確認
aws ec2 describe-regions --output table

# 特定のリソースの存在確認
aws iam get-role --role-name ROLE_NAME
```

## 6. セキュリティのベストプラクティス

### 6.1 認証情報の管理

- AWS CLIの認証情報は定期的にローテーション
- 最小権限の原則に従ったIAMポリシーの設定
- 本番環境では一時的な認証情報の使用を推奨

### 6.2 機密情報の取り扱い

- `terraform.tfvars`ファイルは`.gitignore`に追加
- 機密情報は環境変数やAWS Secrets Managerを使用
- Terraformの`sensitive = true`属性を活用

## まとめ

この記事で紹介した方法を使用することで、TerraformでAWSリソースを管理する際に必要な値を効率的に確認できます。特に、AWS CLIを活用した確認方法は、手動での入力ミスを防ぎ、正確な値を取得するのに役立ちます。

Workload Identity連携などの高度な設定では、OIDC Providerの作成やIAMロールの設定が必要になりますが、これらの手順も段階的に実行することで、安全で確実な設定が可能です。

## 参考資料

- [AWS CLI User Guide](https://docs.aws.amazon.com/cli/latest/userguide/)
- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS IAM Identity Providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
