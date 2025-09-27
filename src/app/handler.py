from typing import Any, Dict

# Lambda環境用の絶対インポート
import router


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    return router.handle_event(event)  # type: ignore[no-any-return]
