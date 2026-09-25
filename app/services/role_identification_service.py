from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository
from app.schemas.role import UserRoleData
from app.services.user_lookup import effective_role_names, find_user_or_404

class RoleIdentificationService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def get_user_role(self, user_id: str) -> UserRoleData:
        # Validate format and retrieve user
        user = find_user_or_404(self.repository, user_id)

        # Retrieve roles (falls back to account_type when no explicit UserRole exists)
        roles = effective_role_names(user)
        primary_role = roles[0]

        return UserRoleData(
            user_id=user.id,
            university_id=user.university_id,
            name=user.name,
            account_type=user.account_type,
            roles=roles,
            primary_role=primary_role
        )
