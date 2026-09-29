import os
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import database_url_for
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


# Set to run the suite against a server database instead of SQLite files, e.g.
#   TEST_DATABASE_URL=postgresql://postgres@localhost:5432/identity_test
# The database's public schema is wiped by the tests, so never point this at real data.
TEST_DATABASE_URL = database_url_for(os.environ["TEST_DATABASE_URL"]) if os.getenv("TEST_DATABASE_URL") else None


def engine_for(url: str) -> Engine:
    return create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})


def reset_test_database() -> None:
    """Drop everything in the server test database (tables, enum types, alembic_version)."""
    engine = engine_for(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def fresh_database_url(tmp_path: Path, name: str) -> str:
    """An empty database for tests that run migrations: a new SQLite file, or the reset server database."""
    if not TEST_DATABASE_URL:
        return f"sqlite:///{(tmp_path / name).as_posix()}"
    reset_test_database()
    return TEST_DATABASE_URL
