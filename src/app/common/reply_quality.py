"""Reply quality assessment and filtering utilities."""

from __future__ import annotations

import re
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class QualityScore:
    """Quality score for a reply."""
    overall_score: float
    length_score: float
    politeness_score: float
    completeness_score: float
    clarity_score: float
    issues: List[str]


def assess_reply_quality(
    reply: str,
    inquiry: str,
    subject: str = ""
) -> QualityScore:
    """
    Assess the quality of a reply based on multiple criteria.

    Args:
        reply: The reply text to assess
        inquiry: The original inquiry text
        subject: The subject of the inquiry

    Returns:
        QualityScore object with detailed scoring
    """
    issues: List[str] = []

    # Length assessment
    length_score = _assess_length(reply, issues)

    # Politeness assessment
    politeness_score = _assess_politeness(reply, issues)

    # Completeness assessment
    completeness_score = _assess_completeness(reply, inquiry, subject, issues)

    # Clarity assessment
    clarity_score = _assess_clarity(reply, issues)

    # Overall score (weighted average)
    overall_score = (
        length_score * 0.2 +
        politeness_score * 0.3 +
        completeness_score * 0.3 +
        clarity_score * 0.2
    )

    return QualityScore(
        overall_score=overall_score,
        length_score=length_score,
        politeness_score=politeness_score,
        completeness_score=completeness_score,
        clarity_score=clarity_score,
        issues=issues
    )


def _assess_length(reply: str, issues: List[str]) -> float:
    """Assess reply length appropriateness."""
    length = len(reply.strip())

    if length < 20:
        issues.append("返信が短すぎます")
        return 0.2
    elif length < 50:
        issues.append("返信がやや短いです")
        return 0.6
    elif length > 2000:
        issues.append("返信が長すぎます")
        return 0.4
    elif length > 1000:
        issues.append("返信がやや長いです")
        return 0.7
    else:
        return 1.0


def _assess_politeness(reply: str, issues: List[str]) -> float:
    """Assess politeness level of the reply."""
    score = 0.0

    # Check for polite expressions
    polite_expressions = [
        "ありがとうございます", "お問い合わせ", "いただき", "させていただきます",
        "お客様", "ご", "いたします", "申し訳ございません", "恐れ入ります"
    ]

    found_polite = sum(1 for expr in polite_expressions if expr in reply)
    score += min(found_polite * 0.2, 0.8)

    # Check for proper endings
    if reply.strip().endswith(("ます", "です", "ございます")):
        score += 0.2
    else:
        issues.append("丁寧語の使用が不十分です")

    # Check for negative politeness indicators
    negative_indicators = ["だ", "である", "じゃない", "ないです"]
    if any(indicator in reply for indicator in negative_indicators):
        issues.append("敬語の使用が不十分です")
        score *= 0.7

    return min(score, 1.0)


def _assess_completeness(
    reply: str, inquiry: str, subject: str, issues: List[str]
) -> float:
    """Assess if the reply addresses the inquiry completely."""
    score = 0.0

    # Check if reply acknowledges the inquiry
    if ("お問い合わせ" in reply or "ご質問" in reply or
            "ご連絡" in reply):
        score += 0.3
    else:
        issues.append("お問い合わせへの言及が不十分です")

    # Check for action items or next steps
    action_indicators = [
        "確認", "調査", "対応", "回答", "ご案内", "お調べ", "お返事",
        "連絡", "ご報告", "お知らせ"
    ]
    if any(indicator in reply for indicator in action_indicators):
        score += 0.4
    else:
        issues.append("具体的な対応方針が不明です")

    # Check for contact information or follow-up
    contact_indicators = [
        "お電話", "メール", "ご連絡", "お問い合わせ"
    ]
    if any(indicator in reply for indicator in contact_indicators):
        score += 0.3
    else:
        issues.append("連絡先やフォローアップの案内がありません")

    return min(score, 1.0)


def _assess_clarity(reply: str, issues: List[str]) -> float:
    """Assess clarity and readability of the reply."""
    score = 1.0

    # Check for overly long sentences
    sentences = re.split(r'[。！？]', reply)
    long_sentences = [s for s in sentences if len(s) > 100]
    if long_sentences:
        issues.append("文章が長すぎて読みにくい箇所があります")
        score -= 0.2

    # Check for proper paragraph breaks
    if len(reply) > 200 and '\n' not in reply:
        issues.append("段落分けが不十分です")
        score -= 0.1

    # Check for repetitive phrases
    words = reply.split()
    if len(words) > 10:
        word_counts: Dict[str, int] = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1

        max_repetition = max(word_counts.values()) if word_counts else 1
        if max_repetition > len(words) * 0.2:
            issues.append("同じ表現の繰り返しが多すぎます")
            score -= 0.2

    return max(score, 0.0)


def filter_quality_replies(
    replies: List[Dict[str, Any]],
    min_score: float = 0.6
) -> List[Dict[str, Any]]:
    """
    Filter replies based on quality score.

    Args:
        replies: List of reply dictionaries
        min_score: Minimum quality score threshold

    Returns:
        Filtered list of high-quality replies
    """
    quality_replies = []

    for reply_data in replies:
        reply_text = reply_data.get("final_reply", "")
        inquiry_text = reply_data.get("body_redacted", "")
        subject = reply_data.get("subject", "")

        if not reply_text or not inquiry_text:
            continue

        quality = assess_reply_quality(reply_text, inquiry_text, subject)

        if quality.overall_score >= min_score:
            # Add quality score to the reply data
            reply_data["quality_score"] = quality.overall_score
            reply_data["quality_issues"] = quality.issues
            quality_replies.append(reply_data)

    # Sort by quality score (highest first)
    quality_replies.sort(key=lambda x: x.get("quality_score", 0), reverse=True)

    return quality_replies


def get_best_examples(
    replies: List[Dict[str, Any]],
    inquiry: str,
    subject: str = "",
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Get the best quality examples for a given inquiry.

    Args:
        replies: List of all available replies
        inquiry: Current inquiry text
        subject: Current inquiry subject
        limit: Maximum number of examples to return

    Returns:
        List of best quality examples
    """
    if not replies:
        return []

    # Filter by quality first
    quality_replies = filter_quality_replies(replies, min_score=0.5)

    if not quality_replies:
        return []

    # Score replies based on similarity to current inquiry
    scored_replies = []
    inquiry_keywords = _extract_keywords(inquiry + " " + subject)

    for reply_data in replies:
        reply_inquiry = reply_data.get("body_redacted", "")
        reply_subject = reply_data.get("subject", "")
        reply_keywords = _extract_keywords(reply_inquiry + " " + reply_subject)

        # Calculate similarity score
        similarity = _calculate_similarity(inquiry_keywords, reply_keywords)
        quality_score = reply_data.get("quality_score", 0.5)

        # Combined score (70% quality, 30% similarity)
        combined_score = quality_score * 0.7 + similarity * 0.3

        scored_replies.append((reply_data, combined_score))

    # Sort by combined score and return top examples
    scored_replies.sort(key=lambda x: x[1], reverse=True)

    return [reply_data for reply_data, score in scored_replies[:limit]]


def _extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text."""
    if not text:
        return set()

    # Remove common stop words
    stop_words = {
        "の", "は", "が", "を", "に", "で", "と", "から", "まで", "について",
        "です", "ます", "お", "ご", "いただき", "ありがとう", "ございます",
        "お問い合わせ", "ご質問", "ご連絡", "お客様", "商品", "サービス"
    }

    # Simple keyword extraction
    words = re.findall(r'[\w\u3040-\u309F\u30A0-\u30FF]+', text.lower())
    keywords = set(words) - stop_words

    return keywords


def _calculate_similarity(keywords1: set, keywords2: set) -> float:
    """Calculate similarity between two sets of keywords."""
    if not keywords1 or not keywords2:
        return 0.0

    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)

    return intersection / union if union > 0 else 0.0
