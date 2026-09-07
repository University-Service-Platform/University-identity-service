from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import re
from typing import Dict, Any

from app.repositories.user_repository import UserRepository
from app.models.user import AccountStatus
from app.schemas.validation import UserValidationData, APIResponse, ErrorDetail

class UserValidationService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    @staticmethod
    def validate_identifier_format(user_id: str) -> bool:
        if not user_id or not isinstance(user_id, str):
            return False
        # Valid user_id must be alphanumeric with optional hyphens/underscores, between 3 and 50 chars
        pattern = r"^[a-zA-Z0-9_-]{3,50}$"
        return bool(re.match(pattern, user_id.strip()))

    def validate_user_account(self, user_id: str, require_active: bool = False) -> UserValidationData:
        # Step 1: Validate identifier format
        if not self.validate_identifier_format(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "INVALID_IDENTIFIER_FORMAT",
                        "message": f"User identifier '{user_id}' has an invalid format."
                    }
                }
            )

        # Step 2: Check user existence (search by ID or university_id)
        user = self.repository.get_by_id(user_id)
        if not user:
            user = self.repository.get_by_university_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": f"User with identifier '{user_id}' was not found."
                    }
                }
            )

        # Step 3: Extract roles
        roles = [r.role.name for r in user.roles if r.role]

        is_active = user.status == AccountStatus.ACTIVE

        # Step 4: If active status is strictly required for this validation context
        if require_active and not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error": {
                        "code": "ACCOUNT_INACTIVE",
                        "message": "User account is inactive."
                    }
                }
            )

        return UserValidationData(
            user_id=user.id,
            university_id=user.university_id,
            name=user.name,
            email=user.email,
            account_type=user.account_type,
            status=user.status,
            is_valid=is_active,
            roles=roles
        )
