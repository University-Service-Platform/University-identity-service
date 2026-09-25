from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.role import Role

# System roles recognised by the platform: (name, description).
# Role names are part of the cross-service contract; other services compare against them.
ROLES: List[Tuple[str, str]] = [
    ("ADMIN", "Administrator Role"),
    ("STAFF", "Staff Member Role"),
    ("STUDENT", "Student Role"),
]


def ensure_reference_data(db: Session) -> None:
    """Idempotently create the system roles. Existing rows are left untouched."""
    for name, description in ROLES:
        if not db.query(Role).filter(Role.name == name).first():
            db.add(Role(name=name, description=description))
    db.commit()
