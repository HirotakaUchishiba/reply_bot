import json
import os
import sys
from typing import Any, Dict


def log_json(level: str, message: str, **kwargs: Any) -> None:
    payload: Dict[str, Any] = {
        "level": level,
        "message": message,
        "stage": os.getenv("STAGE", "dev"),
    }
    if kwargs:
        payload.update(kwargs)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def log_info(message: str, **kwargs: Any) -> None:
    log_json("INFO", message, **kwargs)


def log_error(message: str, **kwargs: Any) -> None:
    log_json("ERROR", message, **kwargs)


