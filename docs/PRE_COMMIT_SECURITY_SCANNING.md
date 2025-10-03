# Pre-commit による秘密情報スキャン機能

## 概要

このプロジェクトでは、Git コミット時に誤って秘密情報（API キー、トークン、パスワードなど）をコミットしてしまうことを防ぐため、pre-commit フックを使用した自動スキャン機能を導入しています。

## 導入されたスキャナー

### 1. Gitleaks
- **目的**: コード内の秘密情報パターンを検出
- **対象**: ステージ済みファイル
- **検出内容**: API キー、トークン、パスワード、秘密鍵など

### 2. TruffleHog
- **目的**: 高精度な秘密情報検出
- **対象**: ステージ済みファイル
- **検出内容**: 検証済みの秘密情報のみを報告

## セットアップ手順

### 1. Pre-commit のインストール

```bash
pip install pre-commit
```

### 2. フックの有効化

```bash
pre-commit install
```

このコマンドにより、`.git/hooks/pre-commit` にフックが設定され、コミット時に自動的にスキャンが実行されます。

### 3. 初回フルスキャン（推奨）

```bash
pre-commit run --all-files
```

既存のファイル全体に対してスキャンを実行し、問題がないことを確認します。

## 使用方法

### 通常のコミット時

```bash
git add .
git commit -m "your commit message"
```

コミット時に自動的にスキャンが実行され、秘密情報が検出された場合はコミットが拒否されます。

### 手動スキャン

```bash
# ステージ済みファイルのみスキャン
pre-commit run

# 全ファイルをスキャン
pre-commit run --all-files

# 特定のフックのみ実行
pre-commit run gitleaks
pre-commit run trufflehog
```

## 設定ファイル

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace

  # Gitleaks secret scanning
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
        name: gitleaks (staged)
        args: ["protect", "--verbose", "--staged"]

  # TruffleHog secret scanning
  - repo: https://github.com/trufflesecurity/trufflehog
    rev: v3.78.0
    hooks:
      - id: trufflehog
        name: trufflehog (staged)
        args: ["filesystem", ".", "--only-verified", "--fail", "--no-update", "--since-commit", "HEAD"]
        stages: [commit]
```

## トラブルシューティング

### 誤検知が発生した場合

1. **検出内容の確認**
   ```bash
   pre-commit run --all-files --verbose
   ```

2. **除外ルールの追加**
   - `.gitleaks.toml` ファイルを作成して除外パターンを定義
   - または、該当ファイルを `.gitignore` に追加

3. **一時的なスキップ**
   ```bash
   git commit -m "your message" --no-verify
   ```
   ⚠️ **注意**: この方法は推奨されません。必ず原因を調査してください。

### よくある誤検知

- テストファイル内のダミー値
- ドキュメント内の例示用の値
- 設定ファイルのテンプレート値

### スキャンが失敗した場合

1. **ツールの更新**
   ```bash
   pre-commit autoupdate
   ```

2. **キャッシュのクリア**
   ```bash
   pre-commit clean
   ```

3. **再インストール**
   ```bash
   pre-commit uninstall
   pre-commit install
   ```

## セキュリティベストプラクティス

### 1. 秘密情報の管理

- **AWS Secrets Manager**: 本番環境の秘密情報
- **Google Secret Manager**: GCP リソースの秘密情報
- **環境変数**: ローカル開発用の設定
- **設定ファイル**: テンプレートのみ（`.example` ファイル）

### 2. コミット前の確認事項

- [ ] ハードコードされた API キーがないか
- [ ] パスワードやトークンが含まれていないか
- [ ] 秘密鍵ファイルが含まれていないか
- [ ] データベース接続文字列に認証情報が含まれていないか

### 3. 緊急時の対応

秘密情報を誤ってコミットしてしまった場合：

1. **即座にコミットを取り消し**
   ```bash
   git reset --soft HEAD~1
   ```

2. **秘密情報を削除して再コミット**
   ```bash
   git add .
   git commit -m "Remove sensitive information"
   ```

3. **リモートにプッシュ済みの場合**
   - GitHub のセキュリティ機能を使用
   - 必要に応じて API キーを再生成

## 継続的改善

### 1. 定期的なスキャン

```bash
# 週次での全ファイルスキャン
pre-commit run --all-files
```

### 2. ルールの更新

```bash
# フックのバージョン更新
pre-commit autoupdate
```

### 3. チーム内での共有

- 新メンバーには必ずセットアップ手順を共有
- 誤検知のパターンをチーム内で共有
- セキュリティインシデントの報告フローを確立

## 参考リンク

- [Pre-commit 公式ドキュメント](https://pre-commit.com/)
- [Gitleaks 公式リポジトリ](https://github.com/gitleaks/gitleaks)
- [TruffleHog 公式リポジトリ](https://github.com/trufflesecurity/trufflehog)
- [GitHub セキュリティ機能](https://docs.github.com/ja/code-security)

## 更新履歴

- 2024-12-24: 初版作成
- 2024-12-24: Gitleaks v8.18.4 と TruffleHog v3.78.0 に対応
