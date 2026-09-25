"""Add users.password_hash for credential-based login

Nullable so existing accounts remain valid; they cannot log in until an
administrator sets a password.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_hash")
