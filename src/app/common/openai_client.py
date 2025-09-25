from __future__ import annotations

from functools import lru_cache
from typing import Optional

from openai import OpenAI

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
def _get_client() -> OpenAI:
    cfg = load_config()
    api_key = resolve_openai_api_key(
        cfg.openai_api_key_secret_arn
    )
    return OpenAI(api_key=api_key)


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
        client = _get_client()
        # Keep response short for latency
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            max_output_tokens=400,
        )
        text = resp.output_text or ""
        return text.strip()
    except Exception as exc:  # pragma: no cover - external call
        log_error("openai generation failed", error=str(exc))
        return ""
