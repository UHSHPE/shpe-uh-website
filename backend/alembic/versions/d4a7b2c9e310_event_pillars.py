"""Add Event.pillars, sourced from the tracker sheet's PILLAR(S) column.

Nullable with no backfill on purpose. The column drives how many points a QR
scan awards, and NULL is a truthful "the sheet's PILLAR(S) cell was blank or
unrecognized" -- which is the majority of live rows -- scoring
pillars.NO_PILLAR_POINTS. The next sheet sync fills in every future event
that does carry a pillar; past events are frozen by sync_events rule 3 and
are meant to stay NULL, because their attendance was already awarded under
the old rule and EventAttendance.points_awarded is an audit trail that a
rule change must never rewrite.

Revision ID: d4a7b2c9e310
Revises: c8d2e4f6a901
"""
from alembic import op
import sqlalchemy as sa


revision = "d4a7b2c9e310"
down_revision = "c8d2e4f6a901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event", sa.Column("pillars", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("event", "pillars")
