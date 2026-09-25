"""Initial identity schema (users, roles, user_roles)

Matches the schema previously created by Base.metadata.create_all() in Sprint 1.
Databases created before migrations were introduced should be marked with
`alembic stamp 0001` instead of being upgraded from scratch.

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

account_type_enum = sa.Enum("STUDENT", "STAFF", name="accounttype")
account_status_enum = sa.Enum("ACTIVE", "INACTIVE", name="accountstatus")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("university_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("account_type", account_type_enum, nullable=False),
        sa.Column("status", account_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_university_id", "users", ["university_id"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_id", "roles", ["id"], unique=False)
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_roles_id", "user_roles", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_roles_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_index("ix_roles_id", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_university_id", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
