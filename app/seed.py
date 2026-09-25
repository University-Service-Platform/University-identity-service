"""
Seed the Identity Service database.

    python -m app.seed          # system roles and permissions (safe for every environment)
    python -m app.seed --demo   # system roles + synthetic demo users

Demo users get the password from the DEMO_USER_PASSWORD environment variable (no password
is stored in source control). Without it they are created without a password and cannot
log in until an administrator sets one.

Run `alembic upgrade head` first. Seeding is idempotent: existing rows are never
modified or deleted, so it is safe to run repeatedly.

All demo data is synthetic. Never load real student or staff records.
"""
import argparse
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.role import Role, UserRole
from app.models.user import AccountStatus, AccountType, User
from app.reference_data import ensure_reference_data

logger = logging.getLogger("identity.seed")


@dataclass(frozen=True)
class DemoUser:
    id: str
    university_id: str
    name: str
    account_type: AccountType
    role: str
    status: AccountStatus = AccountStatus.ACTIVE

    @property
    def email(self) -> str:
        return f"{self.university_id.lower()}@university.example"


DEMO_USERS: List[DemoUser] = [
    DemoUser("usr-admin-001", "ADM001", "Demo System Administrator", AccountType.STAFF, "ADMIN"),
    DemoUser("usr-staff-001", "STF001", "Demo Staff Member", AccountType.STAFF, "STAFF"),
    DemoUser("usr-student-001", "STU001", "Demo Student", AccountType.STUDENT, "STUDENT"),
    DemoUser("usr-student-002", "STU002", "Demo Inactive Student", AccountType.STUDENT, "STUDENT",
             AccountStatus.INACTIVE),
    DemoUser("usr-academic-001", "ACD001", "Demo Academic Staff", AccountType.STAFF, "ACADEMIC_STAFF"),
    DemoUser("usr-adminstaff-001", "ADS001", "Demo Administrative Staff", AccountType.STAFF, "ADMINISTRATIVE_STAFF"),
    DemoUser("usr-servicedesk-001", "SDO001", "Demo Service Desk Officer", AccountType.STAFF, "SERVICE_DESK_OFFICER"),
    DemoUser("usr-technician-001", "TEC001", "Demo Technician", AccountType.STAFF, "TECHNICIAN"),
    DemoUser("usr-resourcemgr-001", "RMG001", "Demo Resource Manager", AccountType.STAFF, "RESOURCE_MANAGER"),
    DemoUser("usr-organizer-001", "EVO001", "Demo Event Organizer", AccountType.STAFF, "EVENT_ORGANIZER"),
]


def _role_id(db: Session, name: str) -> Optional[int]:
    role = db.query(Role).filter(Role.name == name).first()
    return role.id if role else None


def seed_demo_users(db: Session, password: Optional[str] = None) -> int:
    password_hash = hash_password(password) if password else None
    created = 0
    for demo in DEMO_USERS:
        if db.query(User).filter(User.id == demo.id).first():
            continue
        db.add(User(
            id=demo.id,
            university_id=demo.university_id,
            name=demo.name,
            email=demo.email,
            account_type=demo.account_type,
            status=demo.status,
            password_hash=password_hash,
        ))
        db.flush()
        db.add(UserRole(user_id=demo.id, role_id=_role_id(db, demo.role)))
        created += 1
    db.commit()
    return created


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Seed the Identity Service database.")
    parser.add_argument("--demo", action="store_true", help="also create synthetic demo users")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    db = SessionLocal()
    try:
        ensure_reference_data(db)
        logger.info("Reference data (system roles and permissions) is in place.")
        if args.demo:
            password = os.getenv("DEMO_USER_PASSWORD")
            if not password:
                logger.warning("DEMO_USER_PASSWORD is not set: new demo users will not be able to log in.")
            logger.info("Created %d synthetic demo user(s).", seed_demo_users(db, password))
    finally:
        db.close()


if __name__ == "__main__":
    main()
