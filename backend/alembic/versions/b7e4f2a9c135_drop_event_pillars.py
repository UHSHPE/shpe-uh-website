"""Drop Event.pillars -- points now come from the hosting committee (services/points.py).

Downgrade restores an empty column only; the sheet sync no longer parses PILLAR(S).

Revision ID: b7e4f2a9c135
Revises: a3c9e7f1b254
"""
from alembic import op
import sqlalchemy as sa

revision = "b7e4f2a9c135"
down_revision = "a3c9e7f1b254"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("event", "pillars")


def downgrade() -> None:
    op.add_column("event", sa.Column("pillars", sa.String(), nullable=True))
