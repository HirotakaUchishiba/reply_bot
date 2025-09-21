## 序文

  

本書は、「Slack AI Eメールアシスタント」プロジェクトの既存設計文書群（要件定義書 1、実装設計仕様書 2、テスト仕様書 3、UXデザインドシエ 4）を補完し、開発チームが実装に着手するために必要となる、具体的かつ詳細な低レベル仕様、構成値、および技術的契約を定義するものです。本書に記載されるすべての仕様は、既存文書で確立されたアーキテクチャ、要件、およびUX原則に完全準拠しています。

---

## 1. Slack App Manifest (YAML)

  

以下は、Slackアプリの基本構成を定義する manifest.yml の雛形です。app.slack.com でのアプリ作成時にこのYAMLを直接インポートすることで、必要なスコープと設定を迅速に適用できます。

  

YAML

  
  

display_information:  
  name: AI Email Assistant  
  description: AIを活用してメール問い合わせへの返信作成を支援します。  
  background_color: "#2E2D2D"  
features:  
  bot_user:  
    display_name: AI Email Assistant  
    always_online: true  
oauth_config:  
  scopes:  
    bot:  
      - chat:write  
      - commands  
settings:  
  interactivity:  
    is_enabled: true  
    # このURLはTerraformで作成されたAPI GatewayのURLに置き換える必要があります  
    request_url: https://{api_gateway_id}.execute-api.{aws_region}.amazonaws.com/prod/slack/events  
  org_deploy_enabled: false  
  socket_mode_enabled: false  
  token_rotation_enabled: false  
  

Manifest解説:

- chat:write: ボットがチャンネルに通知メッセージを投稿するために必須のスコープです 1。
    
- commands: 将来的なスラッシュコマンド拡張のために予約されています。
    
- request_url: Slackからのインタラクション（ボタンクリック、モーダル送信）ペイロードを受信する唯一のエンドポイントです。このURLは、後述するAPI Gatewayのデプロイ後に確定します 2。
    

---

## 2. API Gateway OpenAPI (OAS3) 定義

  

Slackからのすべてのインタラクションは、単一のHTTPエンドポイントで受信されます。以下にそのエンドポイントのOpenAPI 3.0仕様を示します。

  

YAML

  
  

openapi: 3.0.1  
info:  
  title: Slack AI Email Assistant API  
  version: v1.0  
paths:  
  /slack/events:  
    post:  
      summary: Slack Interactivity Endpoint  
      description: Slackからの全てのインタラクティブペイロード(block_actions, view_submission)を受信する。  
      requestBody:  
        required: true  
        content:  
          application/x-www-form-urlencoded:  
            schema:  
              type: object  
              properties:  
                payload:  
                  type: string  
                  description: "A URL-encoded JSON string containing the Slack event payload."  
      responses:  
        '200':  
          description: "Acknowledgement response to Slack. The actual processing is asynchronous."  
          content:  
            application/json:  
              schema:  
                type: object  
      x-amazon-apigateway-integration:  
        type: "aws_proxy"  
        httpMethod: "POST"  
        uri: "arn:aws:apigateway:{aws_region}:lambda:path/2015-03-31/functions/arn:aws:lambda:{aws_region}:{account_id}:function:{lambda_function_name}/invocations"  
        passthroughBehavior: "when_no_match"  
  

API Gateway解説:

- エンドポイント: /slack/events という単一のパスで、POSTメソッドのみを受け付けます。
    
- 統合タイプ: aws_proxy (Lambdaプロキシ統合) を使用し、受信したリクエスト全体をLambda関数に渡します 2。
    
- 認可: Slackからのリクエストは、リクエストヘッダーに含まれる署名（Signing Secret）をLambda関数内で検証するため、API Gatewayレベルでの認可は設定しません。
    
- 3秒ACK戦略: Slackは3秒以内に応答がないとタイムアウトと見なします。本アーキテクチャでは、API Gateway -> Lambdaの同期呼び出しで即座にHTTP 200 OKを返し、時間のかかる処理（OpenAIコールなど）は非同期で実行するか、Lambda内で完結させます。
    

---

## 3. DynamoDBテーブル仕様書

  

ワークフローの状態を管理するDynamoDBテーブルのスキーマと設定を以下に定義します。

  

|   |   |   |
|---|---|---|
|項目|仕様|根拠・解説|
|テーブル名|SlackAiEmailAssistantState|環境ごとにプレフィックス/サフィックスを付与することを推奨 (例: prod-SlackAiEmailAssistantState)。|
|パーティションキー (PK)|context_id (String)|ワークフローの一意な識別子 2。UUID v4を推奨。|
|ソートキー (SK)|(使用しない)|アクセスパターンが GetItem / PutItem のみのため不要 2。|
|TTL属性名|ttl_timestamp (Number)|この属性に設定されたUnixエポック時間を過ぎるとアイテムは自動削除される 2。|
|キャパシティモード|On-Demand (オンデマンド)|予測不能なトラフィックに適している。|
|保存時の暗号化|有効 (AWS所有のキー)|セキュリティ要件 NFR-SEC-04 を満たす 1。|
|属性スキーマ|||
|context_id|String|(PK) ワークフローID。|
|ttl_timestamp|Number|アイテムの有効期限 (Unixエポック秒)。|
|created_at|String|アイテム作成時刻 (ISO 8601形式)。|
|sender_email|String|元のメールの送信者アドレス。|
|recipient_email|String|元のメールの受信者アドレス (返信時のFromとして使用)。|
|subject|String|メールの件名。|
|body_raw|String|抽出されたプレーンテキストのメール本文。|
|body_redacted|String|PIIリダクション後のメール本文。|
|pii_map|String (JSON)|PIIプレースホルダーと元の値のマッピング。再識別化に必須 2。|

---

## 4. Lambda実装契約書

  

コアビジネスロジックを実行するLambda関数の技術的契約を定義します。

  

|   |   |   |
|---|---|---|
|項目|仕様|根拠・解説|
|関数名|SlackAiEmailAssistantMainHandler|Terraformで管理される。|
|ランタイム|python3.11|AWS Lambda Powertools for Pythonとの互換性が高い 2。|
|ハンドラー|app.lambda_handler|app.py ファイルの lambda_handler 関数を指す。|
|アーキテクチャ|arm64|コスト効率が高い。|
|メモリ|512 MB|初期値。負荷テストに基づき調整。|
|タイムアウト|20秒|OpenAI APIの遅延とSlackの3秒ACKを考慮した値。|
|予約並列数|(設定しない)|初期段階では不要。スロットリング発生時に検討。|
|デッドレターキュー (DLQ)|AsyncProcessingDLQ (SQS)|非同期SESトリガーの信頼性を保証 (NFR-REL-01) 1。|
|依存ライブラリ|aws-lambda-powertools, boto3, presidio-analyzer, presidio-anonymizer, requests|requirements.txt で管理し、Lambdaレイヤーまたはデプロイパッケージに含める。|

イベントルーター インターフェース (概念):

ハンドラーは受信イベントの構造を検査し、適切な処理関数にディスパッチします 2。

  

Python

  
  

# app.py (概念コード)  
def lambda_handler(event, context):  
    # Powertoolsによるロギング、トレーシング、メトリクスの初期化  
     
    if is_ses_event(event):  
        return handle_new_email(event)  
    elif is_slack_block_actions_event(event):  
        return handle_generate_reply_click(event)  
    elif is_slack_view_submission_event(event):  
        return handle_send_email_submission(event)  
    else:  
        logger.error("Unknown event type received")  
        # Slackにエラーを返すか、単に終了するかは要件による  
        return {"statusCode": 400, "body": "Unsupported event type"}  
  

---

## 5. Secrets & 環境変数マトリクス

  

Lambda関数に設定される環境変数と、参照するSecrets Managerのシークレットを定義します。

|   |   |   |
|---|---|---|
|キー (環境変数名)|ソース|説明|
|POWERTOOLS_SERVICE_NAME|環境変数|SlackAiEmailAssistant (構造化ログ用)|
|LOG_LEVEL|環境変数|INFO (prod), DEBUG (dev)|
|DYNAMODB_TABLE_NAME|環境変数|状態を保存するDynamoDBテーブル名。|
|SLACK_CHANNEL_ID|環境変数|新規メール通知を投稿するSlackチャンネルID。|
|SENDER_EMAIL_ADDRESS|環境変数|SESからメールを送信する際の送信元アドレス。|
|OPENAI_API_KEY_SECRET_ARN|環境変数|OpenAI APIキーが格納されたSecrets ManagerのシークレットARN。|
|SLACK_BOT_TOKEN_SECRET_ARN|環境変数|Slack Botトークンが格納されたSecrets ManagerのシークレットARN。|
|SLACK_SIGNING_SECRET_ARN|環境変数|Slackリクエスト署名検証用のシークレットARN。|

---

## 6. PIIリダクション設定表

  

Microsoft Presidioライブラリの設定と、pii_mapのスキーマを定義します。

  

|   |   |   |
|---|---|---|
|項目|仕様|根拠・解説|
|有効化対象エンティティ|EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD_NUMBER|要件 NFR-SEC-01 で指定されたPIIタイプ 1。|
|言語|ja|日本語のテキストを対象とする。|
|プレースホルダー形式|[EMAIL_1], [PHONE_1], [CARD_1]|例: メールは [EMAIL_1]、電話は [PHONE_1]。同一タイプが複数出現する場合は連番を付与（[EMAIL_2] など）。|
|pii_map スキーマ|Dict[str, str]|キーがプレースホルダー、値が元のPII文字列となるJSONオブジェクト。これをシリアライズしてDynamoDBに保存する。例: {"[EMAIL_1]": "test@example.com"}|

---

## 7. 運用Runbook (DLQアラート対応)

  

アラーム名: Critical: AsyncProcessingDLQ has messages

トリガー: SQSキュー AsyncProcessingDLQ の ApproximateNumberOfMessagesVisible メトリクスが 0 を上回る。

目的: SESからトリガーされたLambdaの非同期処理に失敗したイベントの損失を防ぎ (NFR-REL-01)、原因を特定して再処理する。

対応手順:

1. アラート認知と初動 (5分以内):
    

- 担当者はアラートを認知し、対応中であることをチームに通知する。
    
- AWSコンソールで AsyncProcessingDLQ を開き、メッセージが存在することを確認する。自動で再処理されることはないため、手動対応が必須である。
    

2. 原因調査 (30分以内):
    

- DLQからメッセージを1つ表示（ポーリング）し、ペイロード（SESイベントのJSON）を確認する。
    
- ペイロードから messageId などのユニークなIDを特定する。
    
- CloudWatch Logs Insightsで、関連するLambda関数のログをクエリし、エラーの原因を特定する。特に ERROR レベルのログとスタックトレースに注目する。
    
- 原因の分類:
    

- A) 一時的な障害: 外部API (OpenAI) のタイムアウト、AWSの一時的な障害など。
    
- B) 永続的な障害: コードのバグ（例: 不正なデータ形式を処理できない）、設定ミス（例: IAM権限不足）など。
    

3. 復旧対応:
    

- 原因A (一時的) の場合:
    

- 障害が解消されていることを確認する。
    
- SQSコンソールの「再処理を開始」機能（Start DLQ redrive）を使用して、メッセージをソースのLambdaに送り返す。
    

- 原因B (永続的) の場合:
    

- 絶対にメッセージを再処理しないこと。 再処理しても再び失敗し、DLQに戻るだけである。
    
- 開発チームがバグを修正し、修正版をデプロイする。
    
- デプロイが完了した後、上記の手順でメッセージを再処理する。
    

4. 事後対応:
    

- 対応内容をインシデントレポートに記録する。
    
- 再発防止策が必要な場合は、バックログにチケットを作成する。
    

---

## 8. CI/CDワークフロー (GitHub Actions)

  

リポジトリの .github/workflows/deploy.yml として配置するワークフローの雛形です。

  

YAML

  
  

name: Deploy Slack AI Email Assistant  
  
on:  
  push:  
    branches:  
      - main  
  
jobs:  
  test-and-plan:  
    name: Test and Plan  
    runs-on: ubuntu-latest  
    steps:  
      - name: Checkout code  
        uses: actions/checkout@v3  
  
      - name: Setup Python  
        uses: actions/setup-python@v4  
        with:  
          python-version: '3.11'  
  
      - name: Install dependencies  
        run: |  
          python -m pip install --upgrade pip  
          pip install -r requirements.txt  
          pip install flake8 pytest moto  
  
      - name: Lint with flake8  
        run: flake8. --count --select=E9,F63,F7,F82 --show-source --statistics  
  
      - name: Run unit tests with pytest  
        run: pytest  
  
      - name: Setup Terraform  
        uses: hashicorp/setup-terraform@v2  
  
      - name: Configure AWS Credentials  
        uses: aws-actions/configure-aws-credentials@v2  
        with:  
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}  
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}  
          aws-region: ap-northeast-1  
  
      - name: Terraform Init  
        run: terraform init  
  
      - name: Terraform Plan  
        run: terraform plan -out=tfplan  
  
      - name: Upload plan  
        uses: actions/upload-artifact@v3  
        with:  
          name: tfplan  
          path: tfplan  
  
  deploy-to-prod:  
    name: Deploy to Production  
    needs: test-and-plan  
    runs-on: ubuntu-latest  
    environment:  
      name: production  
      url: # API GatewayのURLなどを設定  
    steps:  
      - name: Checkout code  
        uses: actions/checkout@v3  
  
      - name: Download plan  
        uses: actions/download-artifact@v2  
        with:  
          name: tfplan  
  
      - name: Setup Terraform  
        uses: hashicorp/setup-terraform@v2  
  
      - name: Configure AWS Credentials  
        uses: aws-actions/configure-aws-credentials@v2  
        with:  
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}  
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}  
          aws-region: ap-northeast-1  
  
      - name: Terraform Apply  
        run: terraform apply -auto-approve tfplan  
  

---

## 9. Terraform variables.tf と tfvars の例

  

Terraform構成の変数定義と環境ごとの設定例です。

variables.tf:

  

Terraform

  
  

variable "aws_region" {  
  description = "The AWS region to deploy resources in."  
  type        = string  
  default     = "ap-northeast-1"  
}  
  
variable "environment" {  
  description = "The deployment environment (e.g., 'dev', 'prod')."  
  type        = string  
}  
  
variable "slack_channel_id" {  
  description = "The Slack channel ID to post notifications to."  
  type        = string  
}  
  
variable "sender_email_address" {  
  description = "The email address to send replies from."  
  type        = string  
}  
  
#... その他の変数定義...  
  

prod.tfvars (本番環境用):

  

Terraform

  
  

environment = "prod"  
  
slack_channel_id = "C01234ABCDE"  
  
sender_email_address = "support@your-reply-domain.com"  
  
#... その他の本番用変数...  
  

dev.tfvars (開発環境用):

  

Terraform

  
  

environment = "dev"  
  
slack_channel_id = "C98765ZYXWV"  
  
sender_email_address = "dev-support@your-reply-domain.com"  
  
#... その他の開発用変数...  
  

これにより、単一のTerraformコードベースから、terraform apply -var-file="prod.tfvars" のようにコマンドを使い分けることで、複数の環境を安全に管理できます 2。

---

## 10. Presidio Lambda Layer ビルド/デプロイ手順

  

Lambdaデプロイサイズとビルド依存を考慮し、Presidio関連ライブラリはLambda Layerとしてデプロイすることを推奨します。

- ビルド環境: Amazon Linux 2 互換 (manylinux) のDocker上でビルド。
- 構成: `python` ディレクトリ直下にsite-packagesを配置してzip化。

シェル

  
  

docker run --rm -v "$PWD":/var/task public.ecr.aws/lambda/python:3.11 bash -lc "\
  mkdir -p python && pip install presidio-analyzer presidio-anonymizer -t python && zip -r presidio-layer.zip python"

AWS CLI

  
  

aws lambda publish-layer-version \
  --layer-name PresidioLayer \
  --compatible-runtimes python3.11 \
  --zip-file fileb://presidio-layer.zip

Terraform

  
  

resource "aws_lambda_layer_version" "presidio" {
  layer_name          = "PresidioLayer"
  compatible_runtimes = ["python3.11"]
  filename            = "presidio-layer.zip" # CIで生成・アップロード
}

resource "aws_lambda_function" "main_handler" {
  # ...
  layers = [aws_lambda_layer_version.presidio.arn]
}

---

## 11. Slack署名検証と3秒ACK実装

  

Slackからのリクエストは、以下で必ず検証します。

- ヘッダー: `X-Slack-Signature`, `X-Slack-Request-Timestamp`
- 手順: `v0:{timestamp}:{raw_body}` をHMAC-SHA256で署名（鍵はSigning Secret）。`X-Slack-Signature`と一致を検証。
- 時刻乖離: リプレイ防止のため±5分以内を許容。
- 3秒ACK: まずHTTP 200で即応答（空JSON可）。重処理は後段で実行。

擬似コード

  
  

if abs(now - timestamp) > 300: return 401
sig_basestring = f"v0:{timestamp}:{raw_body}"
my_sig = "v0=" + hmac_sha256(signing_secret, sig_basestring)
if not hmac_compare(my_sig, slack_signature): return 401
return 200  # ここでACKし、処理は別ハンドラ/分岐へ

---

## 12. OpenAI モデル/タイムアウト/リトライ（環境別）

  

|   |   |   |
|---|---|---|
|環境|model|パラメータ/運用既定|
|dev|gpt-4o-mini|temperature=0.7, max_tokens=300, timeout=8s, retry=2|
|staging|gpt-4o|temperature=0.7, max_tokens=400, timeout=10s, retry=2|
|prod|gpt-4o|temperature=0.7, max_tokens=500, timeout=10s, retry=3|

環境変数例

  
  

OPENAI_MODEL=gpt-4o
OPENAI_TIMEOUT_SECONDS=10
OPENAI_MAX_TOKENS=500
OPENAI_RETRY=3

---

## 13. SES 本番化手順（送信/受信）

  

送信（Egress）

- ドメイン認証: SPF, DKIM をDNSに設定し検証。
- DMARC: `v=DMARC1; p=none; rua=mailto:dmarc@your-domain` から開始し運用に応じ強化。
- サンドボックス解除: AWSサポートに本番移行申請（ユースケース・送信量・オプトイン方針を明記）。

受信（Ingress）

- SES受信はリージョン制約があるため、受信対応リージョンで構成（例: us-east-1 等）。
- 受信リージョンにLambda/Receipt Ruleを配置。クロスリージョンが必要な場合はSQS/SNSで連携。

---

## 14. CI/CD 詳細（Terraform backend / var-files / Secrets連携）

  

- Terraform Backend: S3 + DynamoDBロックを使用（環境毎にprefix分離）。
- var-files: `-var-file="env/dev.tfvars"` のように環境毎に適用。
- Secrets配布: GitHub Secrets → OIDCでAWSロールにAssume → `aws_secretsmanager_secret` に登録 → LambdaはARN参照。
- Plan/Apply: PRで`terraform plan`をアーティファクト化し、mainマージ時のみ`apply`。

#### 引用文献

1. 要件定義書
    
2. 実装設計仕様書
    
3. テスト仕様書
    
4. UXデザインドシエ
    

**