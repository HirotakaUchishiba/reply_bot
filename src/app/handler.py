from typing import Any, Dict

try:
    # Lambda環境用の絶対インポート
    import router
except ImportError:
    # テスト環境用の相対インポート
    from . import router


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    return router.handle_event(event)  # type: ignore[no-any-return]
