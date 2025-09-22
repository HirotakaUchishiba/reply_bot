import hmac
import time
from hashlib import sha256


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    signature: str,
    body: bytes,
    tolerance: int = 60 * 5,
) -> bool:
    # Protect against replay
    now = int(time.time())
    try:
        ts = int(timestamp)
    except Exception:
        return False
    if abs(now - ts) > tolerance:
        return False

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    computed = "v0=" + hmac.new(
        signing_secret.encode("utf-8"), basestring, sha256
    ).hexdigest()
    # Constant-time compare
    return hmac.compare_digest(computed, signature)
