from sqlalchemy.orm import Session, joinedload
from typing import Optional
from app.models.user import User
from app.models.role import UserRole, Role

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        return (
            self.db.query(User)
            .options(joinedload(User.roles).joinedload(UserRole.role))
            .filter(User.id == user_id)
            .first()
        )

    def get_by_university_id(self, university_id: str) -> Optional[User]:
        return (
            self.db.query(User)
            .options(joinedload(User.roles).joinedload(UserRole.role))
            .filter(User.university_id == university_id)
            .first()
        )

    def get_user_roles(self, user_id: str) -> list[str]:
        user_roles = (
            self.db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id)
            .all()
        )
        return [r[0] for r in user_roles]
