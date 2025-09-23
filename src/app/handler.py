from typing import Any, Dict
from router import handle_event


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    return handle_event(event)  # type: ignore[no-any-return]
