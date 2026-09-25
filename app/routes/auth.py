from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import jwks
from app.database import get_db
from app.dependencies.auth import require_active_account, require_permission
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MessageData,
    MessageResponse,
    PasswordChangeRequest,
    PasswordSetRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.services.user_management_service import UserManagementService

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
    return TokenResponse(success=True, data=AuthService(db).login(credentials.username, credentials.password))


@router.post(
    "/auth/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change Own Password",
    description="Change the authenticated user's password. Requires the current password."
)
def change_password(
    body: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_account)
):
    AuthService(db).change_password(current_user, body.current_password, body.new_password)
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
    UserManagementService(db).set_password(user_id, body.new_password)
    return MessageResponse(success=True, data=MessageData(message=f"Password for user '{user_id}' was set."))


@jwks_router.get(
    "/.well-known/jwks.json",
    status_code=status.HTTP_200_OK,
    summary="JSON Web Key Set",
    description="Public key(s) for verifying Identity Service access tokens (RS256). Empty when HS256 is configured."
)
def get_jwks():
    return jwks()
