from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import burn_password_check, encode_token, hash_password, verify_password
from app.core.time import utc_now
from app.models.user import AccountStatus, User
from app.repositories.permission_repository import PermissionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import CurrentIdentityData, TokenData
from app.services.user_lookup import effective_role_names

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={
        "success": False,
        "error": {
            "code": "INVALID_CREDENTIALS",
            "message": "Invalid university ID/email or password."
        }
    },
    headers={"WWW-Authenticate": "Bearer"}
)


def build_access_claims(user: User) -> dict:
    """
    JWT claims issued at login. Roles are included for routing and UI decisions only:
    they are a snapshot, so services must still validate authorization through the
    Identity Service APIs (roles can change or accounts can be deactivated after issuance).
    """
    return {
        "sub": user.id,
        "university_id": user.university_id,
        "account_type": user.account_type.value,
        "roles": effective_role_names(user),
    }


class AuthService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)
        self.permission_repository = PermissionRepository(db)

    def _find_by_username(self, username: str):
        username = username.strip()
        user = self.repository.get_by_university_id(username)
        if not user and "@" in username:
            user = self.repository.get_by_email(username.lower())
        return user

    def login(self, username: str, password: str) -> TokenData:
        user = self._find_by_username(username)

        # Same response (and similar timing) for unknown users, users without a
        # password and wrong passwords, so accounts cannot be enumerated.
        if not user:
            burn_password_check()
            raise INVALID_CREDENTIALS
        if not verify_password(password, user.password_hash):
            raise INVALID_CREDENTIALS

        if user.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error": {
                        "code": "ACCOUNT_INACTIVE",
                        "message": "Your account is inactive. Please contact an administrator."
                    }
                }
            )

        settings = get_settings()
        claims = build_access_claims(user)
        return TokenData(
            access_token=encode_token(claims),
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            user_id=user.id,
            university_id=user.university_id,
            roles=claims["roles"],
        )

    def current_identity(self, user: User) -> CurrentIdentityData:
        """Identity, roles and permissions of the authenticated user, read live from the Identity DB."""
        roles = effective_role_names(user)
        return CurrentIdentityData(
            user_id=user.id,
            university_id=user.university_id,
            name=user.name,
            email=user.email,
            account_type=user.account_type,
            status=user.status,
            roles=roles,
            primary_role=roles[0],
            permissions=self.permission_repository.get_codes_for_roles(roles),
        )

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "INVALID_CURRENT_PASSWORD",
                        "message": "The current password is incorrect."
                    }
                }
            )
        user.password_hash = hash_password(new_password)
        user.updated_at = utc_now()
        self.repository.update(user)
