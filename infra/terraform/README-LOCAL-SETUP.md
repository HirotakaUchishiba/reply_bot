# ローカル開発環境のセットアップ

このドキュメントは、ローカル開発環境でTerraformを使用する際の設定方法を説明します。

## 🔧 ローカル設定ファイルの作成

### 1. ローカル設定ファイルを作成

```bash
# staging環境用のローカル設定
cp staging.tfvars staging.local.tfvars
```

### 2. 実際の値を設定

`staging.local.tfvars` ファイルを編集して、実際の値を設定してください：

```hcl
# ローカル開発用の設定ファイル
# このファイルはGitにコミットしないでください

# Terraform state configuration (ローカル用の実際の値)
tf_state_bucket         = "your-actual-terraform-state-bucket"
tf_state_key_prefix     = "reply-bot"
tf_state_dynamodb_table = "your-actual-terraform-locks-table"

# SES configuration (ローカルテスト用)
ses_recipients = ["your-actual-email@example.com"]

# Application configuration (ローカルテスト用)
sender_email_address = "your-actual-email@example.com"
slack_channel_id     = "your-actual-slack-channel-id"

# SES Domain Authentication (ローカルテスト用 - 無効化)
# ses_domain_name = "staging.your-reply-domain.com"
# ses_dmarc_email = "dmarc@your-reply-domain.com"
```

## 🚀 使用方法

### Terraformコマンドの実行

```bash
# ローカル設定ファイルを使用してTerraformを実行
terraform plan -var-file=staging.tfvars -var-file=staging.local.tfvars
terraform apply -var-file=staging.tfvars -var-file=staging.local.tfvars
```

### 設定の優先順位

1. `staging.local.tfvars` (最高優先度)
2. `staging.tfvars` (基本設定)
3. デフォルト値

## ⚠️ 重要な注意事項

### セキュリティ
- **`*.local.tfvars` ファイルは絶対にGitにコミットしないでください**
- 機密情報（APIキー、パスワード、個人情報）を含む可能性があります
- `.gitignore` に `*.local.tfvars` が追加されています

### ファイル管理
- ローカル設定ファイルは各開発者の環境に応じて異なります
- チーム間での共有は行わないでください
- 定期的に機密情報の見直しを行ってください

## 🔄 環境別設定

### 開発環境
```bash
terraform plan -var-file=staging.tfvars -var-file=staging.local.tfvars
```

### 本番環境
```bash
# GitHub ActionsやCI/CDで実行
terraform plan -var-file=prod.tfvars
```

## 📝 トラブルシューティング

### よくある問題

1. **設定ファイルが見つからない**
   ```bash
   # ファイルが存在することを確認
   ls -la *.local.tfvars
   ```

2. **変数が正しく読み込まれない**
   ```bash
   # 変数の値を確認
   terraform console
   > var.sender_email_address
   ```

3. **機密情報がGitにコミットされた**
   ```bash
   # 即座にファイルを削除
   git rm --cached *.local.tfvars
   git commit -m "Remove sensitive local configuration"
   ```

---

**最終更新**: 2025年9月26日
**バージョン**: 1.0.0
