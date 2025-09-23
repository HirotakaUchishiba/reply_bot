from __future__ import annotations

from typing import List

import boto3


def send_email(
    sender: str,
    to_addresses: List[str],
    subject: str,
    body: str,
) -> None:
    client = boto3.client("ses")
    client.send_email(
        Source=sender,
        Destination={"ToAddresses": to_addresses},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )
