# Slack AI Eメールアシスタント 📧🤖

OpenAIを活用し、顧客からのEメール問い合わせへの返信業務を自動化・効率化するサーバーレスアプリケーションです。生成された返信文案はSlack上で人間がレビュー、編集、承認する\*\*Human-in-the-Loop (HITL)\*\*のプロセスを組み込んでおり、業務効率と応答品質の両立を実現します。

-----

## 概要

このシステムは、AWS Simple Email Service (SES)で受信した問い合わせメールをトリガーに、AWS Lambda関数がOpenAI APIを利用して返信文案を自動生成します。生成された文案はSlackに通知され、担当者は内容を確認・編集した上で、ボタン一つで実際の返信メールを送信できます。

アーキテクチャはAWS上の完全なサーバーレス・イベント駆動型で構成されており、スケーラビリティとコスト効率に優れています。

-----

## 主な特徴

  * **完全サーバーレス**: AWS Lambda、SES、DynamoDB、API Gatewayを活用し、運用オーバーヘッドを削減。
  * **非同期AI生成**: Cloud Runを活用した非同期処理により、Slack APIの3秒タイムアウト制限を回避し、高品質なAI返信生成を実現。
  * **Human-in-the-Loop (HITL)**: AIが生成した文案をSlack上で人間が承認・編集するプロセスを導入し、品質を担保。
  * **PII（個人識別情報）の自動マスキング**: 外部AIモデルにメール本文を渡す前に、Microsoft Presidioライブラリを用いてPIIを自動的に検出し、プレースホルダーに置き換えます。これにより、機密情報を安全に取り扱います。
  * **Infrastructure as Code (IaC)**: Terraformを用いて全てのインフラをコードで定義し、再現性とバージョン管理を保証。
  * **CI/CDパイプライン**: GitHub Actionsによる自動化されたテストとデプロイパイプラインを構築。
  * **高い回復力**: 非同期処理にデッドレターキュー（DLQ）を設定し、予期せぬエラーによるデータ損失を防止。
  * **優れたオブザーバビリティ**: 構造化ロギングと相関IDにより、リクエストの追跡が容易。ビジネスリスクに直結するSESのレピュテーションメトリクスなど、重要な指標をCloudWatchで監視します。

-----

## アーキテクチャと動作フロー

![全体のフロー図](images/application-flow.png)

### 非同期ワークフロー（推奨）

Slack APIの3秒タイムアウト制限を回避するため、Cloud Runを活用した非同期処理を実装しています：

1. **メール受信**: SES → S3 → Lambda（既存フロー）
2. **Slack通知**: 問い合わせ内容をSlackに通知
3. **返信生成開始**: 「返信文を生成する」ボタンクリック
4. **即座レスポンス**: Lambdaが即座にモーダルを表示（< 1秒）
5. **非同期生成**: Cloud Run JobがバックグラウンドでAI生成（5-15秒）
6. **モーダル更新**: 生成完了後、Slackモーダルを自動更新

詳細は [ASYNC_WORKFLOW_DOCUMENTATION.md](ASYNC_WORKFLOW_DOCUMENTATION.md) を参照してください。

### 従来の同期ワークフロー（フォールバック）

非同期エンドポイントが設定されていない場合、従来の同期処理が実行されます：

本システムは、メール受信（非同期イベント）とSlackからの操作（同期的HTTPリクエスト）という2種類のイベントを単一のLambda関数で処理する「デュアルイングレス」モデルを採用しています。

### 動作シーケンス

1.  **メール受信**: `SES`が指定アドレスへのメールを受信し、`Lambda`関数を非同期で起動します。
2.  **コンテキスト保存**: `Lambda`はメール内容（宛先、件名など）とPIIの対応表（pii\_map）を`DynamoDB`に保存し、一意な`context_id`を取得します。
3.  **Slack通知**: `Lambda`は`context_id`を埋め込んだボタン付きのメッセージをSlackに投稿します。

![Slack通知画面](images/message-notification.png)
4.  **返信生成**: ユーザーがSlackの「返信文を生成する」ボタンをクリックすると、`API Gateway`経由で`Lambda`が起動されます。
5.  **AI連携**: `Lambda`は`context_id`を基に`DynamoDB`からコンテキストを復元し、PIIをマスキングした上でメール本文を`OpenAI` APIに渡し、返信文案を生成させます。
6.  **レビューと編集**: `Lambda`は生成された文案をSlackモーダル（ポップアップウィンドウ）に表示します。ユーザーはこのモーダル上で内容を自由に編集できます。

![返信生成モーダル](images/reply-dialog.png)
7.  **メール送信**: ユーザーが「送信」ボタンをクリックすると、再度`API Gateway`経由で`Lambda`が起動されます。
8.  **最終処理**: `Lambda`は編集された最終的なテキストと`DynamoDB`に保存されていた宛先情報（PIIを復元）を使って、`SES`経由で返信メールを送信します。

-----

## セットアップとデプロイ

### 前提条件

  * AWSアカウント
  * Terraform
  * OpenAI APIキー
  * Slackワークスペースとアプリ作成権限
  * 送信用ドメイン（SES認証用）

### クイックスタート

1. **リポジトリをクローン**
   ```bash
   git clone https://github.com/your-org/reply_bot.git
   cd reply_bot
   ```

2. **GitHub Secretsの設定**
   - [SECRETS_SETUP.md](.github/SECRETS_SETUP.md)の指示に従ってGitHub Secretsを設定

3. **環境設定ファイルの準備**
   - `infra/terraform/staging.tfvars` - ステージング環境設定
   - `infra/terraform/prod.tfvars` - 本番環境設定
   - `infra/terraform/backend.auto.tfvars` - バックエンド設定

4. **デプロイの実行**
   ```bash
   # ステージング環境へのデプロイ
   git push origin develop
   
   # 本番環境へのデプロイ
   git push origin main
   ```

5. **デプロイ後の設定**
   - [SLACK_APP_SETUP.md](.github/SLACK_APP_SETUP.md) - Slackアプリの設定
   - [SES_DOMAIN_SETUP.md](.github/SES_DOMAIN_SETUP.md) - SESドメイン認証
   - [SECRETS_MANAGER_SETUP.md](.github/SECRETS_MANAGER_SETUP.md) - シークレット設定

### 自動化スクリプト

プロジェクトには便利な自動化スクリプトが含まれています：

```bash
# Secrets Managerの設定
./scripts/setup-secrets.sh staging --interactive

# デプロイメントの検証
./scripts/validate-deployment.sh staging --all
```

### 詳細なデプロイ手順

詳細な手順については、[DEPLOYMENT_GUIDE.md](.github/DEPLOYMENT_GUIDE.md)を参照してください。

GitHub Actionsを用いたCI/CDパイプラインも定義されており、リポジトリへのプッシュをトリガーに自動でテストとデプロイが実行されます。

![送信完了メッセージ](images/reply-complete-notification.png)

-----

## セキュリティ

本システムはセキュリティを最優先に設計されています。

  * **IAM最小権限**: Lambda実行ロールには、CloudWatch Logs、DynamoDB、Secrets Manager、SESへのアクセスなど、必要最低限の権限のみが付与されます。
  * **機密情報管理**: OpenAI APIキーなどのシークレットはAWS Secrets Managerで安全に管理されます。
  * **メール送信ドメイン認証**: SESの送信ドメインには、なりすましを防ぎ、到達率を高めるために**SPF**、**DKIM**、**DMARC**レコードの設定が必須です。
  * **データ暗号化**: DynamoDBに保存されるデータは保存時に暗号化（Encryption at Rest）が有効化されます。