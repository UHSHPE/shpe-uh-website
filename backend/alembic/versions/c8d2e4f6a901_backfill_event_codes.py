"""Backfill attendance codes now that event creation owns code generation.

Revision ID: c8d2e4f6a901
Revises: a3f1c9d24e7b
"""
import secrets

from alembic import context, op
import sqlalchemy as sa


revision = "c8d2e4f6a901"
down_revision = "a3f1c9d24e7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("Event code backfill requires an online database connection.")

    # Keep migrations independent of application models and service imports.
    event = sa.table(
        "event",
        sa.column("id", sa.Integer),
        sa.column("sign_in_code", sa.String),
        sa.column("sign_out_code", sa.String),
    )
    connection = op.get_bind()
    missing = sa.or_(
        event.c.sign_in_code.is_(None), event.c.sign_in_code == "",
        event.c.sign_out_code.is_(None), event.c.sign_out_code == "",
    )
    # Include past events (also returned by /events/mine) and soft-deleted
    # events (sheet sync can restore them). Lock selected rows until Alembic
    # commits so another writer cannot change codes between our read/write.
    rows = connection.execute(
        sa.select(event).where(missing).order_by(event.c.id).with_for_update()
    ).mappings().all()
    for row in rows:
        values = {
            column: secrets.token_urlsafe(16)
            for column in ("sign_in_code", "sign_out_code")
            if not row[column]
        }
        connection.execute(
            event.update().where(event.c.id == row["id"]).values(**values)
        )


def downgrade() -> None:
    # Codes may already be printed/shared; retain them when rolling back.
    # The previous app also understands these columns and values.
    pass
