from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from typing import Optional, List, Union

from app.database import get_db
from app.models.user import User, AccountStatus
from app.repositories.user_repository import UserRepository

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development_secret_key_change_in_production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60

security = HTTPBearer(auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authentication credentials were not provided."
                }
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "success": False,
                    "error": {
                        "code": "INVALID_TOKEN",
                        "message": "Authentication token is invalid."
                    }
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Authentication token is invalid or expired."
                }
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    repository = UserRepository(db)
    user = repository.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "Authenticated user no longer exists."
                }
            }
        )

    return user

def require_active_account(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    USM-50 Account Status Authorization Dependency.
    Ensures that only users with an ACTIVE account status are authorized for protected requests.
    Immediately rejects INACTIVE users with 403 Forbidden.
    """
    if current_user.status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": {
                    "code": "ACCOUNT_INACTIVE",
                    "message": "Your account is inactive. Protected operations are forbidden."
                }
            }
        )
    return current_user

class RoleChecker:
    """
    USM-59 / USM-84 Reusable Role-Based Authorization Dependency.
    Checks whether the current active user possesses any of the required allowed roles.
    Never trusts client-supplied roles. Queries trusted Identity DB roles dynamically.
    """
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = [r.upper() for r in allowed_roles]

    def __call__(
        self,
        current_user: User = Depends(require_active_account),
        db: Session = Depends(get_db)
    ) -> User:
        repository = UserRepository(db)
        user_roles = [r.upper() for r in repository.get_user_roles(current_user.id)]
        
        # Fallback to account_type if no explicit UserRole entity exists yet
        if not user_roles:
            user_roles = [current_user.account_type.value.upper()]

        # Check if user has any of the allowed roles
        has_permission = any(role in self.allowed_roles for role in user_roles)
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error": {
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "message": f"User does not have required role permissions: {self.allowed_roles}"
                    }
                }
            )
        return current_user

def require_roles(allowed_roles: List[str]):
    return RoleChecker(allowed_roles)
