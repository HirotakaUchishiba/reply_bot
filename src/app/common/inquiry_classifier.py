# src/app/common/inquiry_classifier.py
from __future__ import annotations


def is_inquiry(subject: str, body: str) -> bool:
    s = (subject or "").lower()
    b = (body or "").lower()

    # 除外（ノイズ・通知・自動送信など）
    negatives = [
        "no-reply", "noreply", "newsletter", "receipt", "notification",
        "do-not-reply", "donotreply", "billing statement", "promo",
        "自動送信", "自動通知", "配信停止", "ニュースレター", "請求書", "領収書",
        "システム通知", "エラー通知", "定期通知", "監視アラート",
    ]
    if any(x in s or x in b for x in negatives):
        return False

    # 強いポジティブ（問い合わせ語・支援要請）
    positives = [
        "問い合わせ", "お問合せ", "お問い合わせ", "質問", "サポート", "トラブル", "サポセン",
        "help", "support", "question", "issue", "trouble", "inquiry",
        "確認したい", "教えて", "お願い", "至急", "至急対応", "キャンセル",
    ]
    if any(x in s or x in b for x in positives):
        return True

    # 疑問表現
    if "?" in b:
        return True
    jp_q = ["でしょうか", "ですか", "いただけますか", "可能でしょうか", "教えてください"]
    if any(x in b for x in jp_q):
        return True

    # 本文が極端に短い場合はノイズとみなす（閾値は調整可）
    return len(b) >= 40
