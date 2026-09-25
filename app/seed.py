"""
Seed the Identity Service database.

    python -m app.seed          # system roles only (safe for every environment)
    python -m app.seed --demo   # system roles + synthetic demo users

Run `alembic upgrade head` first. Seeding is idempotent: existing rows are never
modified or deleted, so it is safe to run repeatedly.

All demo data is synthetic. Never load real student or staff records.
"""
import argparse
import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

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
]


def _role_id(db: Session, name: str) -> Optional[int]:
    role = db.query(Role).filter(Role.name == name).first()
    return role.id if role else None


def seed_demo_users(db: Session) -> int:
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
        logger.info("Reference data (system roles) is in place.")
        if args.demo:
            logger.info("Created %d synthetic demo user(s).", seed_demo_users(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
