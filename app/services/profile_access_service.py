import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.integrations.directory_client import DirectoryClient, DirectoryServiceError, DirectoryServiceUnavailable
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.schemas.directory import AffiliationStatus, AffiliationSummary
from app.schemas.profile import UserProfileData
from app.services.user_lookup import effective_role_names, find_user_or_404

logger = logging.getLogger("identity.profile")

class ProfileAccessService:
    def __init__(self, db: Session, directory: Optional[DirectoryClient] = None):
        self.repository = UserRepository(db)
        self.directory = directory

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

        # Step 4: Department/faculty affiliation from the Directory Service (best effort)
        affiliation, affiliation_status = self._lookup_affiliation(target_user.id)

        # Step 5: Build the profile
        return UserProfileData(
            user_id=target_user.id,
            university_id=target_user.university_id,
            name=target_user.name,
            email=target_user.email,
            account_type=target_user.account_type,
            status=target_user.status,
            roles=effective_role_names(target_user),
            created_at=target_user.created_at,
            affiliation=affiliation,
            affiliation_status=affiliation_status
        )

    def _lookup_affiliation(self, user_id: str) -> Tuple[Optional[AffiliationSummary], AffiliationStatus]:
        """
        The profile is Identity-owned data and must stay available when the Directory
        Service is down, so directory failures degrade to affiliation_status=UNAVAILABLE.
        """
        if not self.directory or not self.directory.is_configured:
            return None, AffiliationStatus.NOT_CONFIGURED
        try:
            affiliation = self.directory.get_user_affiliation(user_id)
        except (DirectoryServiceUnavailable, DirectoryServiceError):
            logger.warning("Affiliation for %s unavailable; returning profile without it.", user_id)
            return None, AffiliationStatus.UNAVAILABLE
        if affiliation is None:
            return None, AffiliationStatus.NONE
        return AffiliationSummary(
            department_id=affiliation.department_id,
            department_name=affiliation.department_name,
            faculty_id=affiliation.faculty_id,
            faculty_name=affiliation.faculty_name,
        ), AffiliationStatus.AVAILABLE
