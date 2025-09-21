## ドキュメント名: 開発ワークフローとGit運用規約

---

### 1. 目的

本ドキュメントは、本プロジェクト「Slack AI Eメールアシスタント」における日々の開発フロー、ブランチ戦略、コミット規約、プッシュ/プルリクエスト運用の実務ルールを定義します。実装は `reply_bot_docs/IMPLEMENTATION_TODO_LIST_&_PROJECT_ROADMAP_DOC.md` の手順に厳密に従い、各タスクを適切な粒度でブランチ化・コミット・プッシュ・PR化することを標準とします。


### 2. 適用範囲と参照

- 本規約は、アプリケーションコード、インフラ（Terraform/IaC）、ドキュメント、テスト、CI/CD 設定に適用します。
- 本ドキュメント策定前提として、以下の資産を全件レビュー済みです。
  - `images/` ディレクトリ内の全画像: `application-flow.png`, `message-notification.png`, `reply-complete-notification.png`, `reply-dialog.png`
  - `README.md`
  - `reply_bot_docs/DEFINITION_OF_REQUIREMENTS_DOC.md`
  - `reply_bot_docs/IMPLEMENTATION_DESIGN_SPECIFICATIONS_DOC.md`
  - `reply_bot_docs/IMPLEMENTATION_SUPPLEMENTARY_MATERIALS_DOC.md`
  - `reply_bot_docs/IMPLEMENTATION_TODO_LIST_&_PROJECT_ROADMAP_DOC.md`


### 3. 開発の基本方針（TODOリスト駆動）

1. 実装対象は常に `IMPLEMENTATION_TODO_LIST_&_PROJECT_ROADMAP_DOC.md` に記載のタスクから選定します。
2. 1タスク = 1ブランチ を原則とし、タスク完了単位でPRを作成します。
3. コミットは意味のある論理単位で細かく行い、動作可能な最小単位を保ちます。
4. プッシュ後はすみやかにPRを作成し、簡潔なタイトルと説明、影響範囲、確認観点、関連ドキュメント/画像を明記します。
5. セキュリティ/可観測性/回復力の必須要件（要件定義・設計仕様のNFR）に反しないことを常に確認します。


### 4. ブランチ戦略

- 長期ブランチ
  - `main`: リリースブランチ（保護対象）。
  - `develop`: 開発統合ブランチ（デフォルト）。

- 短期トピックブランチ（命名規則）
  - フォーマット: `<type>/<scope>-<short-desc>`
  - `type` 一覧（推奨）:
    - `feat`: 機能追加（アプリ/インフラ含む）
    - `fix`: 不具合修正
    - `docs`: ドキュメント変更（本文書含む）
    - `refactor`: リファクタリング（動作仕様不変）
    - `test`: テスト追加/修正
    - `ci`: CI/CD 設定変更
    - `infra`: Terraform/IaC 変更
    - `chore`: 雑務（依存更新、フォーマッタ導入 等）

- 例
  - `feat/slack-modal-open-and-submit`
  - `infra/dynamodb-table-and-ttl`
  - `docs/update-readme-setup-section`
  - `ci/add-terraform-plan-workflow`


### 5. コミット規約（Conventional Commits 準拠）

- 形式
  - `type(scope): subject`
  - 例: `feat(lambda): implement event router for SES and Slack`

- 指針
  - subject は命令形・簡潔に（日本語可）。
  - 1コミット1目的。テスト/ドキュメントの随伴変更は同一目的に含めて可。
  - Body で背景/設計意図/代替案を必要に応じて補足。
  - Footer に関連Issue、BREAKING CHANGE、Co-authored-by 等を記載。

- 例
  - `docs(workflow): add development workflow and git conventions doc`
  - `infra(terraform): add SQS DLQ and wire to lambda`
  - `test(pii): add unit tests for email redaction`


### 6. プッシュとPR作成の運用

- プッシュ
  - 変更は小さく、グリーン状態（lint/test/format）でプッシュ。
  - 機密情報（鍵/ARN/トークン）は絶対にコミットしない。

- PR（Pull Request）
  - タイトル: 先頭に `type:` を付与して要点を端的に。
  - 本文（テンプレート例）:
    - 概要: 何を・なぜ（背景/目的）。
    - 変更点: 箇条書きで主要変更点。
    - 影響範囲: 実行/デプロイ/運用への影響、互換性注意。
    - 動作確認: 再現手順、スクリーンショット/画像（必要に応じて）。
    - テスト: 追加/更新したテストの種類と観点。
    - セキュリティ/コンプライアンス: PII/Secrets/ログ混入有無の確認。
    - 関連: 関連タスク/ドキュメント/Issueへのリンク。

- マージ方針
  - 原則 `Squash and merge`。コミット履歴はPR単位で集約。
  - CI 成功とレビュー承認を必須に設定することを推奨。


### 7. TODOリストとの対応付け（実装開始ルール）

- `IMPLEMENTATION_TODO_LIST_&_PROJECT_ROADMAP_DOC.md` の各セクションに対し、代表ブランチ例を以下の通り推奨します。
  - IaC: `infra/<resource>-<action>` 例) `infra/dynamodb-table-and-ttl`
  - Lambdaロジック: `feat/<domain>-<action>` 例) `feat/event-router-and-ack`
  - Slack連携: `feat/slack-<feature>` 例) `feat/slack-notification-and-modal`
  - CI/CD/テスト: `ci/<concise-desc>`, `test/<area>-<desc>`
  - ドキュメント/運用: `docs/<doc-name>`

- 大型タスクはサブタスクへ分割し、粒度は「半日〜1日で完了する論理単位」を目安にします。


### 8. セキュリティと品質ゲート

- セキュリティ
  - PIIをログ/外部サービスへ送出しない（NFR準拠）。
  - Secretsはコード/リポジトリへ直書き禁止。AWS Secrets Manager 参照。
  - IAMは最小権限。Terraformのポリシー差分をレビュー。

- 品質
  - 静的解析・リント・ユニットテストをローカル/CIで実施。
  - 重要ロジック（イベントルーター、PIIサブシステム、OpenAIコール）は必ずテストを伴う。
  - 5xx やDLQなどの可観測性メトリクス閾値を破らない変更であること。


### 9. 作業コマンド・チートシート

```bash
# ブランチ作成
git checkout -b feat/event-router-and-ack

# 変更のステージングとコミット
git add -A
git commit -m "feat(lambda): implement event router and 3s ack"

# リモートへプッシュ
git push -u origin feat/event-router-and-ack

# （参考）GitHub CLI がある場合のPR作成
# gh pr create -t "feat: implement event router and 3s ack" -b "概要/変更点/確認観点 など"
```


### 10. このドキュメント自体の変更ルール

- 本ドキュメントの更新は `docs/<short-desc>` ブランチで行い、PRテンプレートに従ってレビュー/マージします。
- プロジェクトの運用に影響する変更は、変更理由と既存規約との整合性を明記してください。


---

最終更新者: プロジェクトメンテナ


