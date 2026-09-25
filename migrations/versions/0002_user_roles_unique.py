"""Enforce one row per (user, role) in user_roles

Removes redundant duplicate assignments (keeping the earliest row) before
adding the unique constraint, so existing databases upgrade cleanly.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM user_roles WHERE id NOT IN "
        "(SELECT MIN(id) FROM user_roles GROUP BY user_id, role_id)"
    )
    with op.batch_alter_table("user_roles") as batch_op:
        batch_op.create_unique_constraint("uq_user_roles_user_role", ["user_id", "role_id"])


def downgrade() -> None:
    with op.batch_alter_table("user_roles") as batch_op:
        batch_op.drop_constraint("uq_user_roles_user_role", type_="unique")
