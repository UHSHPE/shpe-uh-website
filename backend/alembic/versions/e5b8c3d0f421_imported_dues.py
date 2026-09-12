"""Add academic-year dues claims imported from the membership spreadsheet."""

from alembic import op
import sqlalchemy as sa

revision = "e5b8c3d0f421"
down_revision = "d4a7b2c9e310"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the imported dues table and its unique membership identity."""
    op.create_table(
        "importeddues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("psid", sa.String(length=7), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("source_sheet_id", sa.String(), nullable=True),
        sa.Column("source_title", sa.String(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("psid", "period_start", name="uq_imported_dues_psid_period"),
    )


def downgrade() -> None:
    """Remove imported dues claims."""
    op.drop_table("importeddues")
