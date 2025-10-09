from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import boto3

try:
    from .reply_quality import get_best_examples, filter_quality_replies
except ImportError:
    # Fallback for testing
    def get_best_examples(replies: List[Dict[str, Any]],
                         inquiry: str,
                         subject: str = "",
                         limit: int = 3) -> List[Dict[str, Any]]:
        return replies[:limit]

    def filter_quality_replies(replies: List[Dict[str, Any]],
                              min_score: float = 0.6) -> List[Dict[str, Any]]:
        return replies


def get_table_name() -> str:
    name = os.getenv("DDB_TABLE_NAME", "")
    if not name:
        raise ValueError("DDB_TABLE_NAME not set")
    return name


def get_context_item(context_id: str) -> Optional[Dict[str, Any]]:
    table = boto3.resource("dynamodb").Table(get_table_name())
    resp = table.get_item(Key={"context_id": context_id})
    return resp.get("Item")


def put_context_item(item: Dict[str, Any]) -> None:
    table = boto3.resource("dynamodb").Table(get_table_name())
    table.put_item(Item=item)


def store_final_reply(
        context_id: str,
        final_reply: str,
        sender_email: str
        ) -> None:

    table = boto3.resource("dynamodb").Table(get_table_name())

    table.update_item(
        Key={"context_id": context_id},
        UpdateExpression=(
            "SET final_reply = :reply, replied_at = :timestamp, "
            "reply_sender = :sender"
        ),
        ExpressionAttributeValues={
            ":reply": final_reply,
            ":timestamp": int(time.time()),
            ":sender": sender_email
        }
    )


def get_recent_replies(limit: int = 5) -> List[Dict[str, Any]]:
    """Get recent replies with quality filtering."""
    table = boto3.resource("dynamodb").Table(get_table_name())
    response = table.scan(
        FilterExpression=(
            "attribute_exists(final_reply) AND "
            "attribute_exists(replied_at)"
        ),
        ProjectionExpression=(
            "context_id, subject, body_redacted, "
            "final_reply, replied_at, sender_email"
        ),
        Limit=limit * 5  # Get more items for quality filtering
    )

    items = response.get("Items", [])

    # Basic quality filtering
    quality_items = []
    for item in items:
        final_reply = item.get("final_reply", "")
        body_redacted = item.get("body_redacted", "")

        # Basic quality checks
        if (len(final_reply) >= 20 and  # Minimum reply length
            len(final_reply) <= 2000 and  # Maximum reply length
            len(body_redacted) >= 10 and  # Minimum inquiry length
            final_reply.strip() and  # Not just whitespace
            body_redacted.strip()):  # Not just whitespace
            quality_items.append(item)

    # Apply advanced quality filtering
    quality_filtered = filter_quality_replies(quality_items, min_score=0.5)

    # Sort by replied_at timestamp (most recent first)
    sorted_items = sorted(
        quality_filtered,
        key=lambda x: x.get("replied_at", 0),
        reverse=True
    )

    return sorted_items[:limit]


def get_similar_replies(
    subject: str,
    body_redacted: str,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """Get replies similar to the current inquiry."""
    table = boto3.resource("dynamodb").Table(get_table_name())
    response = table.scan(
        FilterExpression=(
            "attribute_exists(final_reply) AND "
            "attribute_exists(replied_at)"
        ),
        ProjectionExpression=(
            "context_id, subject, body_redacted, "
            "final_reply, replied_at, sender_email"
        ),
        Limit=50  # Scan more items for similarity matching
    )

    items = response.get("Items", [])

    # Simple similarity scoring based on subject and body keywords
    scored_items = []
    current_keywords = set()

    # Extract keywords from current inquiry
    if subject:
        current_keywords.update(subject.lower().split())
    if body_redacted:
        current_keywords.update(body_redacted.lower().split())

    # Remove common words
    stop_words = {
        "の", "は", "が", "を", "に", "で", "と", "から", "まで", "について",
        "です", "ます", "です", "ます", "お", "ご", "いただき", "ありがとう"
    }
    current_keywords = current_keywords - stop_words

    for item in items:
        item_keywords = set()
        item_subject = item.get("subject", "")
        item_body = item.get("body_redacted", "")

        if item_subject:
            item_keywords.update(item_subject.lower().split())
        if item_body:
            item_keywords.update(item_body.lower().split())

        item_keywords = item_keywords - stop_words

        # Calculate similarity score
        if current_keywords and item_keywords:
            similarity = (
                len(current_keywords & item_keywords) /
                len(current_keywords | item_keywords)
            )
            if similarity > 0.1:  # Minimum similarity threshold
                scored_items.append((item, similarity))

    # Sort by similarity score and timestamp
    scored_items.sort(
        key=lambda x: (x[1], x[0].get("replied_at", 0)), reverse=True
    )

    return [item for item, score in scored_items[:limit]]


def get_best_reply_examples(
    current_inquiry: str,
    current_subject: str = "",
    limit: int = 3
) -> List[Dict[str, Any]]:
    """Get the best quality reply examples for the current inquiry."""
    table = boto3.resource("dynamodb").Table(get_table_name())
    response = table.scan(
        FilterExpression=(
            "attribute_exists(final_reply) AND "
            "attribute_exists(replied_at)"
        ),
        ProjectionExpression=(
            "context_id, subject, body_redacted, "
            "final_reply, replied_at, sender_email"
        ),
        Limit=100  # Scan more items for better selection
    )

    items = response.get("Items", [])

    # Filter out items with insufficient data
    valid_items = []
    for item in items:
        final_reply = item.get("final_reply", "")
        body_redacted = item.get("body_redacted", "")

        if (len(final_reply) >= 20 and
            len(final_reply) <= 2000 and
            len(body_redacted) >= 10 and
            final_reply.strip() and
            body_redacted.strip()):
            valid_items.append(item)

    # Use quality assessment to get best examples
    return get_best_examples(valid_items, current_inquiry, current_subject, limit)
