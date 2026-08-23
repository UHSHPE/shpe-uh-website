"""event: sheet_row identity + soft delete, replacing source_row_id

The old identity was source_row_id = "<ISO date>|<normalized title>" -- derived
from the two fields people edit in the tracker sheet, so every rename or date
change minted a new identity, inserted a second event, and (with no delete
pass) left the stale one on the calendar forever.

The sheet is a fixed skeleton -- rows 1..n pre-laid out by date, chairs fill in
a free row, nothing is ever inserted and nothing shifts -- so the sheet row
number is a stable identity that survives any content edit. See
services/event_tracker_services.sync_events.

This revision doubles as the cleanup for the duplicates already in the table:
every FUTURE sheet-sourced event is soft-deleted here, and the next sync
rebuilds them keyed on their row numbers. Past sheet events are left visible as
history; they come out with sheet_row IS NULL, and sync_events' freeze rule
(never modify an event that has already started) means it never touches them.

Revision ID: a3f1c9d24e7b
Revises: b11fde67a1dd
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d24e7b'
down_revision: Union[str, Sequence[str], None] = 'b11fde67a1dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sheet_row is deliberately NOT unique -- the skeleton reuses slots, so a
    # soft-deleted event and its replacement can both hold row 40.
    op.add_column('event', sa.Column('sheet_row', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_event_sheet_row'), 'event', ['sheet_row'], unique=False)

    op.add_column('event', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_event_deleted_at'), 'event', ['deleted_at'], unique=False)

    # Cleanup + handoff, in that order: hide every future sheet-sourced event
    # (which is every current duplicate) so the next sync can rebuild them from
    # their row numbers. start_time is naive UTC, hence the AT TIME ZONE.
    op.execute(
        """
        UPDATE event
           SET deleted_at = (now() AT TIME ZONE 'utc')
         WHERE source_row_id IS NOT NULL
           AND start_time > (now() AT TIME ZONE 'utc')
        """
    )

    op.drop_index(op.f('ix_event_source_row_id'), table_name='event')
    op.drop_column('event', 'source_row_id')


def downgrade() -> None:
    # source_row_id comes back as an empty column: its values were derived from
    # date+title and are not recoverable from anything this revision kept. A
    # sync after a downgrade would therefore re-insert every sheet event once.
    op.add_column('event', sa.Column('source_row_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.create_index(op.f('ix_event_source_row_id'), 'event', ['source_row_id'], unique=True)

    op.drop_index(op.f('ix_event_deleted_at'), table_name='event')
    op.drop_column('event', 'deleted_at')
    op.drop_index(op.f('ix_event_sheet_row'), table_name='event')
    op.drop_column('event', 'sheet_row')
