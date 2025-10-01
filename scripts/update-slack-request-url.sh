#!/bin/bash

# Slack Request URL更新スクリプト
# Cloud Runデプロイ後にSlackアプリのRequest URLを更新する

set -euo pipefail

# 設定
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/infra/terraform"

# 色付きログ
log_info() {
    echo -e "\033[32m[INFO]\033[0m $1"
}

log_warn() {
    echo -e "\033[33m[WARN]\033[0m $1"
}

log_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

# 使用方法
usage() {
    cat << EOF
使用方法: $0 [OPTIONS]

SlackアプリのRequest URLを更新します。

OPTIONS:
    -e, --environment ENV    環境名 (staging|prod) [デフォルト: staging]
    -u, --url URL           Cloud RunサービスのURL
    -t, --token TOKEN       Slack App Token
    -h, --help              このヘルプを表示

例:
    $0 -e staging -u https://reply-bot-slack-events-staging-xxxxx-uc.a.run.app -t xoxb-xxxxx
    $0 --environment prod --url https://reply-bot-slack-events-prod-xxxxx-uc.a.run.app --token xoxb-xxxxx

EOF
}

# デフォルト値
ENVIRONMENT="staging"
CLOUDRUN_URL=""
SLACK_TOKEN=""

# 引数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -u|--url)
            CLOUDRUN_URL="$2"
            shift 2
            ;;
        -t|--token)
            SLACK_TOKEN="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "不明なオプション: $1"
            usage
            exit 1
            ;;
    esac
done

# 必須パラメータチェック
if [[ -z "$CLOUDRUN_URL" ]]; then
    log_error "Cloud Run URLが指定されていません"
    usage
    exit 1
fi

if [[ -z "$SLACK_TOKEN" ]]; then
    log_error "Slack Tokenが指定されていません"
    usage
    exit 1
fi

# 環境チェック
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "prod" ]]; then
    log_error "環境は 'staging' または 'prod' である必要があります"
    exit 1
fi

log_info "Slack Request URL更新を開始します"
log_info "環境: $ENVIRONMENT"
log_info "Cloud Run URL: $CLOUDRUN_URL"

# Slack Request URL構築
SLACK_REQUEST_URL="${CLOUDRUN_URL}/slack/events"

log_info "新しいRequest URL: $SLACK_REQUEST_URL"

# Slack APIでRequest URLを更新
log_info "Slack APIでRequest URLを更新中..."

# Slack Appの情報を取得
APP_INFO=$(curl -s -H "Authorization: Bearer $SLACK_TOKEN" \
    "https://slack.com/api/apps.manifest.get")

if echo "$APP_INFO" | jq -e '.ok' > /dev/null; then
    log_info "現在のSlack App情報を取得しました"
else
    log_error "Slack App情報の取得に失敗しました"
    echo "$APP_INFO" | jq '.'
    exit 1
fi

# 現在のマニフェストを取得
CURRENT_MANIFEST=$(echo "$APP_INFO" | jq '.manifest')

# Request URLを更新
UPDATED_MANIFEST=$(echo "$CURRENT_MANIFEST" | jq --arg url "$SLACK_REQUEST_URL" '
    .event_subscriptions.request_url = $url |
    .interactivity.request_url = $url
')

# マニフェストを更新
UPDATE_RESULT=$(curl -s -X POST \
    -H "Authorization: Bearer $SLACK_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"manifest\": $UPDATED_MANIFEST}" \
    "https://slack.com/api/apps.manifest.update")

if echo "$UPDATE_RESULT" | jq -e '.ok' > /dev/null; then
    log_info "Slack Request URLの更新が完了しました"
    log_info "更新されたURL: $SLACK_REQUEST_URL"
else
    log_error "Slack Request URLの更新に失敗しました"
    echo "$UPDATE_RESULT" | jq '.'
    exit 1
fi

# 検証: 更新されたURLを確認
log_info "更新結果を検証中..."
VERIFY_RESULT=$(curl -s -H "Authorization: Bearer $SLACK_TOKEN" \
    "https://slack.com/api/apps.manifest.get")

if echo "$VERIFY_RESULT" | jq -e '.ok' > /dev/null; then
    CURRENT_URL=$(echo "$VERIFY_RESULT" | jq -r '.manifest.event_subscriptions.request_url')
    if [[ "$CURRENT_URL" == "$SLACK_REQUEST_URL" ]]; then
        log_info "✅ Request URLの更新が正常に完了しました"
        log_info "現在のURL: $CURRENT_URL"
    else
        log_warn "⚠️  Request URLが期待値と異なります"
        log_warn "期待値: $SLACK_REQUEST_URL"
        log_warn "実際値: $CURRENT_URL"
    fi
else
    log_error "更新結果の検証に失敗しました"
    echo "$VERIFY_RESULT" | jq '.'
    exit 1
fi

log_info "Slack Request URL更新が完了しました"
