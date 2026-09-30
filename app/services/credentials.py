"""Password changes and sign-in lockout, shared by every path that sets or checks a password."""
from datetime import datetime, timedelta

from app.core.security import hash_password
from app.core.time import utc_now
from app.models.user import User

# After this many wrong passwords in a row the account can't sign in for LOCKOUT_DURATION
MAX_FAILED_LOGINS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def set_new_password(user: User, new_password: str) -> None:
    """
    Store a new password. Tokens issued before now stop working for the Identity Service, and a
    sign-in lockout is lifted (a password reset is how a locked-out user gets back in).
    """
    now = utc_now()
    user.password_hash = hash_password(new_password)
    # Whole seconds, because a token's iat is whole seconds: a token issued later in this
    # same second must stay valid
    user.password_changed_at = now.replace(microsecond=0)
    user.updated_at = now
    user.failed_login_count = 0
    user.locked_until = None


def issued_before_password_change(user: User, issued_at: object) -> bool:
    """True when a token (iat, seconds since the epoch) predates the user's last password change."""
    if user.password_changed_at is None or not isinstance(issued_at, (int, float)):
        return False
    changed = (user.password_changed_at - datetime(1970, 1, 1)).total_seconds()
    return issued_at < changed


def is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > utc_now()


def record_failed_login(user: User) -> bool:
    """Count a wrong password; returns True when this attempt locks the account."""
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= MAX_FAILED_LOGINS:
        user.failed_login_count = 0
        user.locked_until = utc_now() + LOCKOUT_DURATION
        return True
    return False
