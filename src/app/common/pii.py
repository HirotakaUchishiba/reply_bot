from __future__ import annotations

import re
from typing import Dict, Tuple

try:
    from presidio_analyzer import AnalyzerEngine
    _HAS_PRESIDIO = True
except Exception:  # pragma: no cover - optional in runtime via layer
    _HAS_PRESIDIO = False

# Expose analyzer/anonymizer symbols for tests to patch if needed
analyzer = None  # type: ignore[assignment]
anonymizer = None  # type: ignore[assignment]


EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
PHONE_RE = re.compile(
    r"(?:(?:\+?\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?"
    r"\d{2,4}[ -]?\d{2,4}[ -]?\d{3,4})"
)
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")


def redact_and_map(text: str) -> Tuple[str, Dict[str, str]]:
    pii_map: Dict[str, str] = {}
    if not text:
        return "", pii_map

    if _HAS_PRESIDIO:
        # Prefer a patched/shared analyzer if provided; otherwise create one
        engine = analyzer if analyzer is not None else AnalyzerEngine()
        results = engine.analyze(text=text, language="ja")
        # Normalize entity types to stable keys used across impl and tests
        type_map = {
            "EMAIL_ADDRESS": "EMAIL",
            "PHONE_NUMBER": "PHONE",
            "CREDIT_CARD_NUMBER": "CARD",
        }
        counters: Dict[str, int] = {}
        redacted = text
        # Sort results by start index descending to safely replace
        for r in sorted(results, key=lambda r: r.start, reverse=True):
            entity_type = getattr(r, "entity_type", "")
            key = type_map.get(entity_type, entity_type)
            if not key:
                continue
            counters[key] = counters.get(key, 0) + 1
            placeholder = f"[{key}_{counters[key]}]"
            start = getattr(r, "start", None)
            end = getattr(r, "end", None)
            if start is None or end is None:
                continue
            pii_map[placeholder] = text[start:end]
            redacted = redacted[:start] + placeholder + redacted[end:]
        return redacted, pii_map

    # Fallback regex-based
    counters = {"EMAIL": 0, "PHONE": 0, "CARD": 0}

    def _sub(pattern: re.Pattern[str], key: str, s: str) -> str:
        def repl(m: re.Match[str]) -> str:
            counters[key] += 1
            ph = f"[{key}_{counters[key]}]"
            pii_map[ph] = m.group(0)
            return ph

        return pattern.sub(repl, s)

    redacted = text
    redacted = _sub(EMAIL_RE, "EMAIL", redacted)
    redacted = _sub(PHONE_RE, "PHONE", redacted)
    redacted = _sub(CARD_RE, "CARD", redacted)
    return redacted, pii_map


def reidentify(text: str, pii_map: Dict[str, str]) -> str:
    if not pii_map:
        return text
    out = text
    for placeholder, original in pii_map.items():
        out = out.replace(placeholder, original)
    return out
