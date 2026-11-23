"""Add Event.is_committee_meeting -- chair-created, sign-in-only meetings.

server_default false: every existing event is a sheet or hand-added event, never a meeting.

Revision ID: c4f8a1d6e273
Revises: a3c9e1f4b702
"""
from alembic import op
import sqlalchemy as sa

revision = "c4f8a1d6e273"
down_revision = "a3c9e1f4b702"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event",
        sa.Column("is_committee_meeting", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("event", "is_committee_meeting")
