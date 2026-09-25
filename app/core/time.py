from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Current UTC time as a naive datetime.
    Replaces the deprecated datetime.utcnow() while keeping stored values identical
    (the existing columns are timezone-naive and hold UTC).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
