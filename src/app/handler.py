from typing import Any, Dict
import router


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    return router.handle_event(event)  # type: ignore[no-any-return]
