from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import uuid
import re
from typing import List, Optional
from datetime import datetime

from app.models.user import User, AccountStatus, AccountType
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate, UserResponse

class UserManagementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    @staticmethod
    def validate_identifier_format(user_id: str) -> bool:
        if not user_id or not isinstance(user_id, str):
            return False
        pattern = r"^[a-zA-Z0-9_-]{3,50}$"
        return bool(re.match(pattern, user_id.strip()))

    def _format_user_response(self, user: User) -> UserResponse:
        roles = [r.role.name for r in user.roles if r.role]
        if not roles and user.account_type:
            roles = [user.account_type.value]
        return UserResponse(
            id=user.id,
            university_id=user.university_id,
            name=user.name,
            email=user.email,
            account_type=user.account_type,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=roles
        )

    def create_user(self, user_in: UserCreate) -> UserResponse:
        # Step 1: Validate university_id format
        if not self.validate_identifier_format(user_in.university_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "INVALID_IDENTIFIER_FORMAT",
                        "message": f"University identifier '{user_in.university_id}' has an invalid format."
                    }
                }
            )

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
        new_user = User(
            id=f"usr-{uuid.uuid4().hex[:12]}",
            university_id=user_in.university_id.strip(),
            name=user_in.name.strip(),
            email=str(user_in.email).strip().lower(),
            account_type=user_in.account_type,
            status=AccountStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        persisted_user = self.repository.create(new_user)
        return self._format_user_response(persisted_user)

    def list_users(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        users = self.repository.list_all(skip=skip, limit=limit)
        return [self._format_user_response(u) for u in users]

    def get_user_by_id(self, user_id: str) -> UserResponse:
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

        return self._format_user_response(user)

    def update_user(self, user_id: str, user_update: UserUpdate) -> UserResponse:
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

        user.updated_at = datetime.utcnow()
        updated_user = self.repository.update(user)
        return self._format_user_response(updated_user)

    def update_user_status(self, user_id: str, new_status: AccountStatus) -> UserResponse:
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

        user.status = new_status
        user.updated_at = datetime.utcnow()
        updated_user = self.repository.update(user)
        return self._format_user_response(updated_user)

    def delete_user(self, user_id: str) -> None:
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

        self.repository.delete(user)
