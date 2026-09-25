from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.permission import Permission, RolePermission
from app.models.role import Role

# System roles recognised by the platform: (name, description).
# Role names are part of the cross-service contract; other services compare against them.
# ADMIN, STAFF and STUDENT are the Sprint 1 roles; the others are the platform roles
# defined in the University Services Management Platform case specification.
ROLES: List[Tuple[str, str]] = [
    ("ADMIN", "Administrator Role"),
    ("STAFF", "Staff Member Role"),
    ("STUDENT", "Student Role"),
    ("ACADEMIC_STAFF", "Academic staff: reserves teaching or meeting resources, submits requests and organizes events"),
    ("ADMINISTRATIVE_STAFF", "Administrative staff: manages service information, approves reservations and publishes announcements"),
    ("SERVICE_DESK_OFFICER", "Service desk officer: reviews, categorizes and prioritizes incoming service requests"),
    ("TECHNICIAN", "Technician / maintenance staff: works on assigned work orders"),
    ("RESOURCE_MANAGER", "Resource manager: maintains facilities, equipment, availability and reservation approvals"),
    ("EVENT_ORGANIZER", "Event organizer: creates events and manages capacity, eligibility and registrations"),
]

# Permissions for operations owned by the Identity Service: (code, description).
PERMISSIONS: List[Tuple[str, str]] = [
    ("profile:read_own", "View own profile"),
    ("users:read", "List user accounts and view any user profile"),
    ("users:manage", "Create, update and delete user accounts"),
    ("users:manage_status", "Activate or deactivate user accounts"),
    ("roles:read", "View the role and permission catalogue"),
    ("roles:assign", "Assign, update and revoke user roles"),
    ("audit:read", "View the audit log of administrative and security actions"),
]

# Which Identity Service permissions each role grants.
# This mirrors the role rules enforced on the Sprint 1 endpoints (e.g. ADMIN and STAFF may
# list users); tests/test_role_catalogue.py verifies the two stay consistent.
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "ADMIN": [code for code, _ in PERMISSIONS],
    "STAFF": ["profile:read_own", "users:read", "roles:read"],
    "STUDENT": ["profile:read_own"],
    "ACADEMIC_STAFF": ["profile:read_own"],
    "ADMINISTRATIVE_STAFF": ["profile:read_own"],
    "SERVICE_DESK_OFFICER": ["profile:read_own"],
    "TECHNICIAN": ["profile:read_own"],
    "RESOURCE_MANAGER": ["profile:read_own"],
    "EVENT_ORGANIZER": ["profile:read_own"],
}


def ensure_reference_data(db: Session) -> None:
    """
    Idempotently create the system roles, permissions and role-permission grants.
    Missing rows are added; existing rows are never modified or removed.
    """
    for name, description in ROLES:
        if not db.query(Role).filter(Role.name == name).first():
            db.add(Role(name=name, description=description))

    for code, description in PERMISSIONS:
        if not db.query(Permission).filter(Permission.code == code).first():
            db.add(Permission(code=code, description=description))
    db.flush()

    for role_name, codes in ROLE_PERMISSIONS.items():
        role = db.query(Role).filter(Role.name == role_name).one()
        for code in codes:
            permission = db.query(Permission).filter(Permission.code == code).one()
            exists = (
                db.query(RolePermission)
                .filter(RolePermission.role_id == role.id, RolePermission.permission_id == permission.id)
                .first()
            )
            if not exists:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.commit()
