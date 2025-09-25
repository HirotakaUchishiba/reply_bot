# Slackアプリ設定ガイド

このガイドでは、Slack AI Email AssistantのSlackアプリを設定する手順を説明します。

## 前提条件

- Slackワークスペースの管理者権限
- デプロイ済みのAPI GatewayエンドポイントURL

## 手順

### 1. Slackアプリの作成

1. [Slack API](https://api.slack.com/apps)にアクセス
2. **Create New App** をクリック
3. **From an app manifest** を選択
4. ワークスペースを選択
5. 以下のmanifest.ymlの内容をコピー&ペースト

### 2. Manifest.ymlの設定

```yaml
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
    request_url: https://YOUR_API_GATEWAY_ID.execute-api.ap-northeast-1.amazonaws.com/slack/events
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

### 3. API Gateway URLの設定

1. デプロイ完了後、Terraformの出力からAPI Gateway URLを取得：
   ```bash
   cd infra/terraform
   terraform output api_gateway_url
   ```

2. Slackアプリの設定画面で：
   - **Interactivity & Shortcuts** セクションに移動
   - **Request URL** を上記で取得したURLに設定
   - **Save Changes** をクリック

### 4. Bot Tokenの取得

1. **OAuth & Permissions** セクションに移動
2. **Install to Workspace** をクリック
3. 権限を確認して **Allow** をクリック
4. **Bot User OAuth Token** をコピー（`xoxb-` で始まる）

### 5. Signing Secretの取得

1. **Basic Information** セクションに移動
2. **Signing Secret** セクションで **Show** をクリック
3. シークレットをコピー

### 6. Secrets Managerへの設定

取得した認証情報をAWS Secrets Managerに設定：

```bash
# Bot TokenとSigning SecretをJSON形式で設定
aws secretsmanager put-secret-value \
  --secret-id "reply-bot/stg/slack/app-creds" \
  --secret-string '{"bot_token":"xoxb-your-bot-token","signing_secret":"your-signing-secret"}'
```

### 7. チャンネルIDの取得

1. Slackで通知を受け取りたいチャンネルに移動
2. チャンネル名をクリック
3. **About** タブでチャンネルIDをコピー（`C` で始まる）

### 8. 動作確認

1. 設定したチャンネルで `/invite @AI Email Assistant` を実行
2. テストメールを送信して通知が届くことを確認
3. 「返信文を生成する」ボタンが動作することを確認

## トラブルシューティング

### よくある問題

1. **Request URL verification failed**
   - API Gateway URLが正しいか確認
   - Lambda関数が正常にデプロイされているか確認
   - Slack署名検証が正しく実装されているか確認

2. **Bot Tokenが無効**
   - Bot Tokenが正しくコピーされているか確認
   - Secrets Managerに正しく設定されているか確認
   - アプリがワークスペースにインストールされているか確認

3. **チャンネルに通知が届かない**
   - チャンネルIDが正しいか確認
   - ボットがチャンネルに招待されているか確認
   - 環境変数 `SLACK_CHANNEL_ID` が正しく設定されているか確認

## セキュリティの考慮事項

- Bot TokenとSigning Secretは機密情報として扱う
- 本番環境とステージング環境で異なるアプリを使用することを推奨
- 定期的にトークンのローテーションを検討する
