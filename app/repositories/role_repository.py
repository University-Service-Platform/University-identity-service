from sqlalchemy.orm import Session
from typing import Optional, List
from app.models.role import Role, UserRole

class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_role_by_id(self, role_id: int) -> Optional[Role]:
        return self.db.query(Role).filter(Role.id == role_id).first()

    def get_role_by_name(self, role_name: str) -> Optional[Role]:
        return self.db.query(Role).filter(Role.name == role_name).first()

    def list_roles(self) -> List[Role]:
        return self.db.query(Role).all()

    def get_user_role_link(self, user_id: str, role_id: int) -> Optional[UserRole]:
        return (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.role_id == role_id)
            .first()
        )

    def add_user_role(self, user_role: UserRole) -> UserRole:
        self.db.add(user_role)
        self.db.commit()
        self.db.refresh(user_role)
        return user_role

    def remove_user_role(self, user_role: UserRole) -> None:
        self.db.delete(user_role)
        self.db.commit()
