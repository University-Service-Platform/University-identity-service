from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, UserRole
from app.reference_data import ROLES, ensure_reference_data
from app.seed import DEMO_USERS, seed_demo_users
from tests.helpers import auth_header, create_user

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"


def alembic_config(db_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def test_migrations_create_schema_matching_models(migrated_db_url):
    config = alembic_config(migrated_db_url)
    command.upgrade(config, "head")

    tables = set(inspect(create_engine(migrated_db_url)).get_table_names())
    assert {"users", "roles", "user_roles", "alembic_version"} <= tables

    # Fails if the models and the migration history have drifted apart.
    command.check(config)


def test_migrations_downgrade_to_empty_database(migrated_db_url):
    config = alembic_config(migrated_db_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    tables = set(inspect(create_engine(migrated_db_url)).get_table_names())
    assert tables <= {"alembic_version"}


def test_unique_constraint_migration_removes_duplicate_assignments(migrated_db_url):
    config = alembic_config(migrated_db_url)
    command.upgrade(config, "0001")

    engine = create_engine(migrated_db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (id, university_id, name, email, account_type, status) "
            "VALUES ('usr-dup-1', 'DUP001', 'Dup User', 'dup@university.example', 'STAFF', 'ACTIVE')"
        ))
        conn.execute(text("INSERT INTO roles (id, name) VALUES (1, 'ADMIN')"))
        conn.execute(text("INSERT INTO user_roles (user_id, role_id) VALUES ('usr-dup-1', 1), ('usr-dup-1', 1)"))

    command.upgrade(config, "head")

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM user_roles WHERE user_id = 'usr-dup-1'")).scalar()
    assert count == 1


def test_seed_is_idempotent_and_assigns_demo_roles(migrated_db_url):
    command.upgrade(alembic_config(migrated_db_url), "head")
    session = sessionmaker(bind=create_engine(migrated_db_url))()
    try:
        for _ in range(2):
            ensure_reference_data(session)
            seed_demo_users(session)

        assert session.query(Role).count() == len(ROLES)
        assert session.query(UserRole).count() == len(DEMO_USERS)
    finally:
        session.close()


def test_foreign_keys_are_enforced_on_sqlite(db_session):
    db_session.add(UserRole(user_id="usr-missing-999", role_id=12345))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_update_to_already_assigned_role_returns_conflict(client, db_session):
    create_user(db_session, "usr-admin-mig-01", role="ADMIN")
    target = create_user(db_session, "usr-target-mig-02", role="STAFF")
    db_session.add(UserRole(user_id=target.id, role_id=db_session.query(Role).filter_by(name="ADMIN").one().id))
    db_session.commit()

    response = client.put(
        f"/users/{target.id}/roles",
        json={"old_role_name": "STAFF", "new_role_name": "ADMIN"},
        headers=auth_header("usr-admin-mig-01"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROLE_ALREADY_ASSIGNED"
