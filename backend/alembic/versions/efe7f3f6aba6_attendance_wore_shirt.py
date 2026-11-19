"""Add EventAttendance.wore_shirt -- the GM shirt answer.

Nullable with no backfill: existing rows were never asked, which is what NULL means.

Revision ID: efe7f3f6aba6
Revises: b7e4f2a9c135
"""
from alembic import op
import sqlalchemy as sa

revision = "efe7f3f6aba6"
down_revision = "b7e4f2a9c135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eventattendance", sa.Column("wore_shirt", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("eventattendance", "wore_shirt")
