from typing import Iterable, List

from sqlalchemy.orm import Session

from app.models.permission import Permission, RolePermission
from app.models.role import Role

class PermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_codes_for_roles(self, role_names: Iterable[str]) -> List[str]:
        names = [name.upper() for name in role_names]
        if not names:
            return []
        rows = (
            self.db.query(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .filter(Role.name.in_(names))
            .distinct()
            .all()
        )
        return sorted(row[0] for row in rows)
