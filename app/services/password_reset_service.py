"""
Forgot-password flow: a one-time link sent by email, then a new password set with it.

    request_reset(email)  -> the email to send, or None. The caller answers the same way either
                             way, and sends the email after responding, so neither the answer
                             nor its timing shows whether an account exists.
    reset_password(token, new_password)

Tokens are 256-bit random values; only their SHA-256 hash is stored. A token works once, expires
after PASSWORD_RESET_TOKEN_MINUTES, and asking for a new link spends the older ones.
"""
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from html import escape
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import utc_now
from app.demo_accounts import PROTECTED_IDENTIFIERS, ensure_not_protected_demo_account
from app.models.password_reset import PasswordResetToken
from app.models.user import AccountStatus, User
from app.repositories.user_repository import UserRepository
from app.services import audit_service
from app.services.audit_service import AuditService
from app.services.credentials import set_new_password

logger = logging.getLogger("identity.password_reset")

# At most this many links per account in the window, so the endpoint can't be used to flood an inbox
MAX_REQUESTS_PER_WINDOW = 3
REQUEST_WINDOW = timedelta(minutes=15)

INVALID_RESET_TOKEN = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={"success": False, "error": {
        "code": "INVALID_RESET_TOKEN",
        "message": "This password reset link is invalid or has expired. Please request a new one."}},
)


@dataclass(frozen=True)
class ResetEmail:
    to: str
    subject: str
    text: str
    html: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_email(user: User, link: str, minutes: int) -> ResetEmail:
    first_name = user.name.split(" ")[0] if user.name else ""
    greeting = f"Hello {first_name}," if first_name else "Hello,"
    text = (
        f"{greeting}\n\n"
        "We received a request to reset the password for your University Services Platform account "
        f"({user.university_id}).\n\n"
        f"Set a new password here (the link works once and expires in {minutes} minutes):\n{link}\n\n"
        "If you didn't ask for this, you can ignore this email; your password stays the same."
    )
    safe_link = escape(link, quote=True)
    html = (
        f"<p>{escape(greeting)}</p>"
        "<p>We received a request to reset the password for your University Services Platform account "
        f"(<strong>{escape(user.university_id)}</strong>).</p>"
        f'<p><a href="{safe_link}" style="display:inline-block;padding:10px 18px;background:#1e40af;'
        f'color:#ffffff;border-radius:6px;text-decoration:none">Set a new password</a></p>'
        f"<p>The link works once and expires in {minutes} minutes. If the button doesn't work, "
        f'copy this address into your browser:<br><a href="{safe_link}">{escape(link)}</a></p>'
        "<p>If you didn't ask for this, you can ignore this email; your password stays the same.</p>"
    )
    return ResetEmail(to=user.email, subject="Reset your University Services password", text=text, html=html)


class PasswordResetService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def _find_user(self, identifier: str) -> Optional[User]:
        identifier = identifier.strip()
        if "@" in identifier:
            return self.users.get_by_email(identifier.lower())
        return self.users.get_by_university_id(identifier)

    def request_reset(self, identifier: str) -> Optional[ResetEmail]:
        settings = get_settings()
        user = self._find_user(identifier)
        if user is None or user.status != AccountStatus.ACTIVE:
            return None
        # Shared demo accounts keep their password (and their addresses can't receive mail)
        if settings.protect_demo_users and user.id.lower() in PROTECTED_IDENTIFIERS:
            return None

        now = utc_now()
        recent = (self.db.query(PasswordResetToken)
                  .filter(PasswordResetToken.user_id == user.id,
                          PasswordResetToken.created_at > now - REQUEST_WINDOW)
                  .count())
        if recent >= MAX_REQUESTS_PER_WINDOW:
            logger.info("Password reset rate limit reached for user %s", user.id)
            return None

        # Only the newest link works
        (self.db.query(PasswordResetToken)
         .filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
         .update({PasswordResetToken.used_at: now}, synchronize_session=False))

        token = secrets.token_urlsafe(32)
        minutes = settings.password_reset_token_minutes
        self.db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(token), created_at=now,
                                       expires_at=now + timedelta(minutes=minutes)))
        self.db.commit()
        AuditService(self.db).record(user.id, audit_service.PASSWORD_RESET_REQUESTED, "USER", user.id)

        if not settings.password_reset_url:
            logger.warning("PASSWORD_RESET_URL is not set, so no reset email can be sent for user %s", user.id)
            return None
        separator = "&" if "?" in settings.password_reset_url else "?"
        return _build_email(user, f"{settings.password_reset_url}{separator}token={token}", minutes)

    def reset_password(self, token: str, new_password: str) -> None:
        record = (self.db.query(PasswordResetToken)
                  .filter(PasswordResetToken.token_hash == hash_token(token.strip()))
                  .first())
        now = utc_now()
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise INVALID_RESET_TOKEN
        user = record.user
        if user is None or user.status != AccountStatus.ACTIVE:
            raise INVALID_RESET_TOKEN
        ensure_not_protected_demo_account(user.id)

        set_new_password(user, new_password)
        # Spend this link and any other open one for the account
        (self.db.query(PasswordResetToken)
         .filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
         .update({PasswordResetToken.used_at: now}, synchronize_session=False))
        self.db.commit()
        AuditService(self.db).record(user.id, audit_service.PASSWORD_RESET_COMPLETED, "USER", user.id)
