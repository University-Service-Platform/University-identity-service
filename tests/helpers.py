from typing import Optional

from app.dependencies.auth import create_access_token
from app.models.role import Role, UserRole
from app.models.user import AccountStatus, AccountType, User


def get_or_create_role(db, name: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(name=name, description=f"{name} role")
        db.add(role)
        db.commit()
        db.refresh(role)
    return role


def create_user(
    db,
    user_id: str,
    role: Optional[str] = None,
    account_type: AccountType = AccountType.STAFF,
    status: AccountStatus = AccountStatus.ACTIVE,
) -> User:
    """Insert a synthetic user (optionally with one assigned role) directly into the test DB."""
    user = User(
        id=user_id,
        university_id=user_id.upper().replace("USR-", "UNI-"),
        name=f"Test {user_id}",
        email=f"{user_id}@test.university.lk",
        account_type=account_type,
        status=status,
    )
    db.add(user)
    db.commit()
    if role:
        db.add(UserRole(user_id=user_id, role_id=get_or_create_role(db, role).id))
        db.commit()
    db.refresh(user)
    return user


def auth_header(user_id: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}
