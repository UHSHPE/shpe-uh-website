"""Make EventAttendance.signed_in_at nullable -- sign-out without a sign-in is allowed.

No backfill: every existing row came from a sign-in scan, so none are NULL.

Revision ID: a3c9e1f4b702
Revises: efe7f3f6aba6
"""
from alembic import op
import sqlalchemy as sa

revision = "a3c9e1f4b702"
down_revision = "efe7f3f6aba6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("eventattendance", "signed_in_at", existing_type=sa.DateTime(), nullable=True)


def downgrade() -> None:
    # Fails if any sign-out-only rows exist; delete or backfill them first.
    op.alter_column("eventattendance", "signed_in_at", existing_type=sa.DateTime(), nullable=False)
