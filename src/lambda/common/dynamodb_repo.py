from __future__ import annotations

import os
from typing import Any, Dict, Optional

import boto3


def get_table_name() -> str:
    name = os.getenv("DDB_TABLE_NAME", "")
    if not name:
        raise ValueError("DDB_TABLE_NAME not set")
    return name


def get_context_item(context_id: str) -> Optional[Dict[str, Any]]:
    table = boto3.resource("dynamodb").Table(get_table_name())
    resp = table.get_item(Key={"context_id": context_id})
    return resp.get("Item")
