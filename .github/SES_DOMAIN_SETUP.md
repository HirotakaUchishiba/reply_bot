# SES送信ドメイン認証設定ガイド

このガイドでは、AWS SESで送信ドメインの認証（SPF、DKIM、DMARC）を設定する手順を説明します。

## 前提条件

- ドメインのDNS管理権限
- AWS SESコンソールへのアクセス権限
- 送信に使用するドメイン（例：your-reply-domain.com）

## 手順

### 1. SESでドメインの認証

1. [AWS SES Console](https://console.aws.amazon.com/ses/)にアクセス
2. **Verified identities** セクションに移動
3. **Create identity** をクリック
4. **Domain** を選択し、ドメイン名を入力
5. **Create identity** をクリック

### 2. SPFレコードの設定

1. SESコンソールで作成したドメインを選択
2. **Authentication** タブで **SPF** セクションを確認
3. DNSプロバイダーで以下のSPFレコードを追加：

```
TXT レコード:
名前: @ (またはドメイン名)
値: v=spf1 include:amazonses.com ~all
```

### 3. DKIM認証の設定

1. SESコンソールで **DKIM** セクションに移動
2. **Edit** をクリック
3. **Easy DKIM** を選択
4. **Generate DKIM settings** をクリック
5. 表示された3つのCNAMEレコードをDNSに追加：

```
CNAME レコード例:
名前: [selector1]._domainkey
値: [selector1].dkim.amazonses.com

名前: [selector2]._domainkey
値: [selector2].dkim.amazonses.com

名前: [selector3]._domainkey
値: [selector3].dkim.amazonses.com
```

### 4. DMARCポリシーの設定

1. DNSプロバイダーで以下のDMARCレコードを追加：

```
TXT レコード:
名前: _dmarc
値: v=DMARC1; p=none; rua=mailto:dmarc@your-reply-domain.com; ruf=mailto:dmarc@your-reply-domain.com; fo=1
```

**注意**: 本番環境では `p=quarantine` または `p=reject` に変更することを推奨

### 5. 認証状況の確認

1. SESコンソールで各認証項目のステータスを確認
2. すべての項目が **Verified** になるまで待機（最大72時間）
3. **Sending statistics** で送信レピュテーションを監視

## 環境別設定

### ステージング環境
- ドメイン: `staging.your-reply-domain.com`
- DMARC: `p=none` (監視モード)

### 本番環境
- ドメイン: `your-reply-domain.com`
- DMARC: `p=quarantine` または `p=reject`

## トラブルシューティング

### よくある問題

1. **SPFレコードが認識されない**
   - DNSの伝播に時間がかかる場合があります（最大48時間）
   - SPFレコードの構文が正しいか確認
   - 既存のSPFレコードと競合していないか確認

2. **DKIM認証が失敗する**
   - CNAMEレコードが正しく設定されているか確認
   - セレクター名が正確にコピーされているか確認
   - DNSの伝播を待つ

3. **DMARCレポートが届かない**
   - レポート用メールアドレスが有効か確認
   - DMARCレコードの構文が正しいか確認

## セキュリティの考慮事項

- DMARCポリシーは段階的に厳しくする（none → quarantine → reject）
- 定期的にDMARCレポートを確認し、認証失敗の原因を調査
- 送信レピュテーションを継続的に監視
- 不審な送信活動がないかログを確認

## 監視とアラート

以下のメトリクスをCloudWatchで監視：

- `Reputation.BounceRate` - バウンス率（5%以下を維持）
- `Reputation.ComplaintRate` - 苦情率（0.1%以下を維持）
- `Send` - 送信数
- `Bounce` - バウンス数
- `Complaint` - 苦情数

## 参考リンク

- [AWS SES Developer Guide](https://docs.aws.amazon.com/ses/latest/dg/)
- [SPF Record Syntax](https://tools.ietf.org/html/rfc7208)
- [DKIM Specification](https://tools.ietf.org/html/rfc6376)
- [DMARC Specification](https://tools.ietf.org/html/rfc7489)
