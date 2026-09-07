from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import re
from app.repositories.user_repository import UserRepository
from app.schemas.role import UserRoleData

class RoleIdentificationService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    @staticmethod
    def validate_identifier_format(user_id: str) -> bool:
        if not user_id or not isinstance(user_id, str):
            return False
        pattern = r"^[a-zA-Z0-9_-]{3,50}$"
        return bool(re.match(pattern, user_id.strip()))

    def get_user_role(self, user_id: str) -> UserRoleData:
        # Validate format
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

        # Retrieve user
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

        # Retrieve roles
        roles = [r.role.name for r in user.roles if r.role]
        if not roles:
            # Fallback to user account_type as primary role if no explicit UserRole entity exists
            roles = [user.account_type.value]

        primary_role = roles[0]

        return UserRoleData(
            user_id=user.id,
            university_id=user.university_id,
            name=user.name,
            account_type=user.account_type,
            roles=roles,
            primary_role=primary_role
        )
