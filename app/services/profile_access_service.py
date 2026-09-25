from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.schemas.profile import UserProfileData
from app.services.user_lookup import effective_role_names, find_user_or_404

class ProfileAccessService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def get_user_profile(self, target_user_id: str, requester: User) -> UserProfileData:
        # Steps 1-2: Validate identifier format and fetch target user profile
        target_user = find_user_or_404(self.repository, target_user_id, resource_label="User profile")

        # Step 3: Access Control Authorization
        # Check if requester is self
        is_self = (requester.id == target_user.id) or (requester.university_id == target_user.university_id)

        # Check if requester has ADMIN or STAFF privileges
        requester_roles = [r.upper() for r in effective_role_names(requester)]
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
        return UserProfileData(
            user_id=target_user.id,
            university_id=target_user.university_id,
            name=target_user.name,
            email=target_user.email,
            account_type=target_user.account_type,
            status=target_user.status,
            roles=effective_role_names(target_user),
            created_at=target_user.created_at
        )
