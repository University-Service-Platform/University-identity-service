from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
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

    def get_by_email(self, email: str) -> Optional[User]:
        return (
            self.db.query(User)
            .options(joinedload(User.roles).joinedload(UserRole.role))
            .filter(User.email == email)
            .first()
        )

    def list_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        return (
            self.db.query(User)
            .options(joinedload(User.roles).joinedload(UserRole.role))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_user_roles(self, user_id: str) -> List[str]:
        user_roles = (
            self.db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id)
            .all()
        )
        return [r[0] for r in user_roles]

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()
