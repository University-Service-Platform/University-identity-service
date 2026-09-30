import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.core.security import jwks
from app.database import get_db
from app.demo_accounts import ensure_not_protected_demo_account
from app.dependencies.auth import require_active_account, require_permission
from app.models.user import User
from app.schemas.auth import (
    CurrentIdentityResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageData,
    MessageResponse,
    PasswordChangeRequest,
    PasswordSetRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.integrations.email_sender import EmailSender, get_email_sender
from app.services.password_reset_service import PasswordResetService, ResetEmail
from app.services import audit_service
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.user_management_service import UserManagementService

logger = logging.getLogger("identity.auth")

router = APIRouter(tags=["Authentication"])

# Served at the service root: the standard location token verifiers look for.
jwks_router = APIRouter(tags=["Authentication"])


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log In",
    description="Authenticate with university ID (or email) and password and receive a signed JWT access token. "
                "Inactive accounts are rejected with 403 ACCOUNT_INACTIVE."
)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    token = AuthService(db).login(credentials.username, credentials.password)
    AuditService(db).record(token.user_id, audit_service.LOGIN_SUCCEEDED, "USER", token.user_id)
    return TokenResponse(success=True, data=token)


@router.get(
    "/auth/me",
    response_model=CurrentIdentityResponse,
    status_code=status.HTTP_200_OK,
    summary="Current Identity",
    description="Return the authenticated user's identity, roles and permissions for role-aware navigation. "
                "Values are read live from the Identity DB, so role changes apply immediately."
)
def get_current_identity(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_account)
):
    return CurrentIdentityResponse(success=True, data=AuthService(db).current_identity(current_user))


RESET_REQUESTED_MESSAGE = ("If an account with that email exists, we've sent a link to reset its password. "
                           "Check your inbox and spam folder.")


def _send_reset_email(sender: EmailSender, email: ResetEmail) -> None:
    try:
        sender.send(email.to, email.subject, email.text, email.html)
    except Exception:  # a failed email must never surface to the requester
        logger.exception("Password reset email could not be sent")


@router.post(
    "/auth/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Forgot Password",
    description="Email a one-time link for setting a new password. Always answers the same way, whether or not "
                "the account exists, so it can't be used to discover accounts. Public (no token)."
)
def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sender: Optional[EmailSender] = Depends(get_email_sender),
):
    email = PasswordResetService(db).request_reset(body.email)
    if email is not None:
        if sender is None:
            logger.warning("EMAIL_PROVIDER is not set, so the password reset email was not sent")
        else:
            # Sent after the response, so the response time doesn't show whether the account exists
            background_tasks.add_task(_send_reset_email, sender, email)
    return MessageResponse(success=True, data=MessageData(message=RESET_REQUESTED_MESSAGE))


@router.post(
    "/auth/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset Password",
    description="Set a new password with the token from the emailed link. The link works once. "
                "Invalid, used or expired links get 400 INVALID_RESET_TOKEN. Public (no token)."
)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    PasswordResetService(db).reset_password(body.token, body.new_password)
    return MessageResponse(success=True, data=MessageData(message="Your password has been changed. You can sign in now."))


@router.post(
    "/auth/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change Own Password",
    description="Change the authenticated user's password. Requires the current password. Every session that "
                "started before the change, this one included, must sign in again (401 SESSION_EXPIRED)."
)
def change_password(
    body: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_account)
):
    ensure_not_protected_demo_account(current_user.id)
    AuthService(db).change_password(current_user, body.current_password, body.new_password)
    AuditService(db).record(current_user.id, audit_service.PASSWORD_CHANGED, "USER", current_user.id)
    return MessageResponse(success=True, data=MessageData(message="Password changed successfully."))


@router.put(
    "/users/{user_id}/password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Set User Password",
    description="Set or reset a user's password. Requires the 'users:manage' permission."
)
def set_user_password(
    user_id: str,
    body: PasswordSetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage"))
):
    ensure_not_protected_demo_account(user_id)
    target = UserManagementService(db).set_password(user_id, body.new_password)
    AuditService(db).record(current_user.id, audit_service.PASSWORD_SET, "USER", target.id)
    return MessageResponse(success=True, data=MessageData(message=f"Password for user '{user_id}' was set."))


@jwks_router.get(
    "/.well-known/jwks.json",
    status_code=status.HTTP_200_OK,
    summary="JSON Web Key Set",
    description="Public key(s) for verifying Identity Service access tokens (RS256). Empty when HS256 is configured."
)
def get_jwks():
    return jwks()
