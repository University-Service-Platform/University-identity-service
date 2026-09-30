"""Add password_changed_at and sign-in lockout columns to users

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_changed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("locked_until")
        batch.drop_column("failed_login_count")
        batch.drop_column("password_changed_at")
