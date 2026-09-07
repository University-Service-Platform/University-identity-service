from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import re
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.schemas.profile import UserProfileData

class ProfileAccessService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    @staticmethod
    def validate_identifier_format(user_id: str) -> bool:
        if not user_id or not isinstance(user_id, str):
            return False
        pattern = r"^[a-zA-Z0-9_-]{3,50}$"
        return bool(re.match(pattern, user_id.strip()))

    def get_user_profile(self, target_user_id: str, requester: User) -> UserProfileData:
        # Step 1: Validate identifier format
        if not self.validate_identifier_format(target_user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "INVALID_IDENTIFIER_FORMAT",
                        "message": f"User identifier '{target_user_id}' has an invalid format."
                    }
                }
            )

        # Step 2: Fetch target user profile
        target_user = self.repository.get_by_id(target_user_id)
        if not target_user:
            target_user = self.repository.get_by_university_id(target_user_id)

        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": f"User profile with identifier '{target_user_id}' was not found."
                    }
                }
            )

        # Step 3: Access Control Authorization
        # Check if requester is self
        is_self = (requester.id == target_user.id) or (requester.university_id == target_user.university_id)

        # Check if requester has ADMIN or STAFF privileges
        requester_roles = [r.upper() for r in self.repository.get_user_roles(requester.id)]
        if not requester_roles:
            requester_roles = [requester.account_type.value.upper()]

        is_authorized_manager = any(role in ["ADMIN", "STAFF"] for role in requester_roles)

        if not is_self and not is_authorized_manager:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN_PROFILE_ACCESS",
                        "message": "You are not authorized to view another user's profile."
                    }
                }
            )

        # Step 4: Extract roles for response
        target_roles = [r.role.name for r in target_user.roles if r.role]
        if not target_roles:
            target_roles = [target_user.account_type.value]

        return UserProfileData(
            user_id=target_user.id,
            university_id=target_user.university_id,
            name=target_user.name,
            email=target_user.email,
            account_type=target_user.account_type,
            status=target_user.status,
            roles=target_roles,
            created_at=target_user.created_at
        )
