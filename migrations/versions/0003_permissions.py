"""Add permissions and role_permissions

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permissions_id", "permissions", ["id"], unique=False)
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )
    op.create_index("ix_role_permissions_id", "role_permissions", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_role_permissions_id", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("ix_permissions_code", table_name="permissions")
    op.drop_index("ix_permissions_id", table_name="permissions")
    op.drop_table("permissions")
