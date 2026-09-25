from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import uuid
from typing import List

from app.core.security import hash_password
from app.core.time import utc_now
from app.models.user import User, AccountStatus
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.user_lookup import effective_role_names, find_user_or_404, require_valid_identifier

class UserManagementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def _format_user_response(self, user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            university_id=user.university_id,
            name=user.name,
            email=user.email,
            account_type=user.account_type,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=effective_role_names(user)
        )

    def create_user(self, user_in: UserCreate) -> UserResponse:
        # Step 1: Validate university_id format
        require_valid_identifier(user_in.university_id, label="University identifier")

        # Step 2: Check university_id uniqueness
        if self.repository.get_by_university_id(user_in.university_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "success": False,
                    "error": {
                        "code": "UNIVERSITY_ID_ALREADY_EXISTS",
                        "message": f"User with university ID '{user_in.university_id}' already exists."
                    }
                }
            )

        # Step 3: Check email uniqueness
        if self.repository.get_by_email(str(user_in.email)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "success": False,
                    "error": {
                        "code": "EMAIL_ALREADY_EXISTS",
                        "message": f"User with email '{user_in.email}' already exists."
                    }
                }
            )

        # Step 4: Create User instance
        now = utc_now()
        new_user = User(
            id=f"usr-{uuid.uuid4().hex[:12]}",
            university_id=user_in.university_id.strip(),
            name=user_in.name.strip(),
            email=str(user_in.email).strip().lower(),
            account_type=user_in.account_type,
            status=AccountStatus.ACTIVE,
            password_hash=hash_password(user_in.password) if user_in.password else None,
            created_at=now,
            updated_at=now
        )

        persisted_user = self.repository.create(new_user)
        return self._format_user_response(persisted_user)

    def list_users(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        users = self.repository.list_all(skip=skip, limit=limit)
        return [self._format_user_response(u) for u in users]

    def get_user_by_id(self, user_id: str) -> UserResponse:
        user = find_user_or_404(self.repository, user_id)
        return self._format_user_response(user)

    def update_user(self, user_id: str, user_update: UserUpdate) -> UserResponse:
        user = find_user_or_404(self.repository, user_id)

        # Check email uniqueness if email is being updated
        if user_update.email is not None:
            email_str = str(user_update.email).strip().lower()
            existing_with_email = self.repository.get_by_email(email_str)
            if existing_with_email and existing_with_email.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "success": False,
                        "error": {
                            "code": "EMAIL_ALREADY_EXISTS",
                            "message": f"User with email '{email_str}' already exists."
                        }
                    }
                )
            user.email = email_str

        if user_update.name is not None:
            user.name = user_update.name.strip()

        if user_update.account_type is not None:
            user.account_type = user_update.account_type

        user.updated_at = utc_now()
        updated_user = self.repository.update(user)
        return self._format_user_response(updated_user)

    def set_password(self, user_id: str, new_password: str) -> User:
        user = find_user_or_404(self.repository, user_id)
        user.password_hash = hash_password(new_password)
        user.updated_at = utc_now()
        return self.repository.update(user)

    def update_user_status(self, user_id: str, new_status: AccountStatus) -> UserResponse:
        user = find_user_or_404(self.repository, user_id)

        user.status = new_status
        user.updated_at = utc_now()
        updated_user = self.repository.update(user)
        return self._format_user_response(updated_user)

    def delete_user(self, user_id: str) -> None:
        user = find_user_or_404(self.repository, user_id)
        self.repository.delete(user)
