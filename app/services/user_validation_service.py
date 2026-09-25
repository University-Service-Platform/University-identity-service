from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional

from app.repositories.user_repository import UserRepository
from app.models.user import AccountStatus
from app.schemas.validation import UserValidationData
from app.services.user_lookup import effective_role_names, find_user_or_404

class UserValidationService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def validate_user_account(
        self,
        user_id: str,
        require_active: bool = False,
        required_role: Optional[str] = None
    ) -> UserValidationData:
        """
        USM-42 & USM-124 Inter-Service User Identity & Role Validation.
        Validates user existence, account status, role relationships, and optional required role authorization.
        Enables Groups 6, 7, and 8 to validate identity/roles without direct DB access.
        """
        # Steps 1-2: Validate identifier format and check user existence (by ID or university_id)
        user = find_user_or_404(self.repository, user_id)

        # Step 3: Extract roles (with account_type fallback if no explicit UserRole mapping)
        roles = effective_role_names(user)

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

        # Step 5: Evaluate role authorization for requested role (USM-124)
        is_authorized = True
        if required_role:
            norm_req_role = required_role.strip().upper()
            is_authorized = any(r.upper() == norm_req_role for r in roles)

        return UserValidationData(
            user_id=user.id,
            university_id=user.university_id,
            name=user.name,
            email=user.email,
            account_type=user.account_type,
            status=user.status,
            is_valid=is_active,
            roles=roles,
            is_authorized=is_authorized,
            required_role_checked=required_role.strip().upper() if required_role else None
        )
