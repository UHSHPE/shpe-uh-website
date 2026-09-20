"""Store dues status on the member instead of deriving it per request.

Revision ID: f7a2d5c8b613
Revises: e5b8c3d0f421

Backfills only the CURRENT membership period, reproducing what the old
derivation answered. Earlier periods are dropped because nothing ever read
them, and the flag has no room to record which year it belongs to — that is
what reset_dues.py handles every May 30.
"""
from datetime import datetime, timezone

from alembic import context, op
import sqlalchemy as sa


revision = "f7a2d5c8b613"
down_revision = "e5b8c3d0f421"
branch_labels = None
depends_on = None

DUES_PRODUCT_NAME = "T-Shirt Dues"
DUES_RESET_MONTH = 5
DUES_RESET_DAY = 30

# Both sources of a paid claim, as raw SQL so the migration stays independent
# of application models. "user" and "order" are reserved words in Postgres.
BACKFILL = sa.text(
    """
    UPDATE "user" SET has_paid_dues = true WHERE id IN (
        SELECT o.user_id FROM "order" o
          JOIN orderitem oi ON oi.order_id = o.id
         WHERE oi.product_name = :dues_product
           AND o.status <> 'cancelled'
           AND o.created_at >= :period
           AND o.user_id IS NOT NULL
        UNION
        SELECT u.id FROM "user" u
          JOIN importeddues d ON d.psid = u.psid
         WHERE d.verified = true
           AND d.period_start = :period
    )
    """
)


def current_period_start() -> datetime:
    """The most recent May 30, mirroring shop_services.current_dues_period_start."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reset_this_year = datetime(now.year, DUES_RESET_MONTH, DUES_RESET_DAY)
    if now >= reset_this_year:
        return reset_this_year
    return datetime(now.year - 1, DUES_RESET_MONTH, DUES_RESET_DAY)


def upgrade() -> None:
    """Add the column and mark everyone the old derivation counted as paid."""
    if context.is_offline_mode():
        raise RuntimeError("Dues backfill requires an online database connection.")

    op.add_column(
        "user",
        sa.Column("has_paid_dues", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.get_bind().execute(
        BACKFILL, {"dues_product": DUES_PRODUCT_NAME, "period": current_period_start()}
    )
    op.alter_column("user", "has_paid_dues", server_default=None)


def downgrade() -> None:
    """Drop the column; orders and imported claims still hold the same facts."""
    op.drop_column("user", "has_paid_dues")
