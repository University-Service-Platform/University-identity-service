from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.role import Role
from app.repositories.role_repository import RoleRepository
from app.schemas.role import RoleCatalogueEntry

class RoleCatalogueService:
    def __init__(self, db: Session):
        self.role_repository = RoleRepository(db)

    @staticmethod
    def _to_entry(role: Role) -> RoleCatalogueEntry:
        return RoleCatalogueEntry(
            name=role.name,
            description=role.description,
            permissions=sorted(link.permission.code for link in role.permissions if link.permission),
        )

    def list_roles(self) -> List[RoleCatalogueEntry]:
        roles = sorted(self.role_repository.list_roles(), key=lambda r: r.name)
        return [self._to_entry(role) for role in roles]

    def get_role(self, role_name: str) -> RoleCatalogueEntry:
        normalized = role_name.strip().upper()
        role = self.role_repository.get_role_by_name(normalized)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "ROLE_NOT_FOUND",
                        "message": f"Role '{normalized}' does not exist."
                    }
                }
            )
        return self._to_entry(role)
