from __future__ import annotations

from functools import lru_cache
from typing import Optional

import json
import urllib.request
import urllib.error

try:
    # Lambda環境用の絶対インポート
    from common.config import load_config
    from common.logging import log_error
    from common.secrets import resolve_openai_api_key
except ImportError:
    # テスト環境用の相対インポート
    from .config import load_config
    from .logging import log_error
    from .secrets import resolve_openai_api_key


@lru_cache(maxsize=1)
def _get_api_key() -> str:
    cfg = load_config()
    return resolve_openai_api_key(cfg.openai_api_key_secret_arn)


def generate_reply_draft(
    redacted_body: str,
    tone: Optional[str] = None,
) -> str:
    """
    Generate a Japanese reply draft from redacted text.
    Do not include PII; input is already redacted.
    """
    if not redacted_body:
        return ""
    lines = [
        "あなたは日本語のCS担当者です。以下の問い合わせに対し、",
        "丁寧で簡潔な返信文案を日本語で作成してください。",
        "- 会社のブランドトーンに合う丁寧語",
        "- 不確実な点は確認依頼として記載",
        "- 箇条書き可",
        "- 件名行は不要",
        "",
        "問い合わせ本文（機微情報はプレースホルダーに置換済み）：",
        redacted_body,
        "",
    ]
    if tone:
        lines.append(f"希望するトーン: {tone}")
        lines.append("")
    prompt = "\n".join(lines)

    try:
        api_key = _get_api_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 300,
        }
        req = urllib.request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(raw)
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = (message or {}).get("content", "")
        return str(content or "").strip()
    except Exception as exc:  # pragma: no cover - external call
        log_error("openai generation failed", error=str(exc))
        return ""
