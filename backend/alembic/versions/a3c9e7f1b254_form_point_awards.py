"""Add points awarded from Google Form responses."""

from alembic import op
import sqlalchemy as sa

revision = "a3c9e7f1b254"
down_revision = "bde8a16f7e59"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "formpointaward",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spreadsheet_id", sa.String(), nullable=False),
        sa.Column("gid", sa.Integer(), nullable=False),
        sa.Column("member_key", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("index_row", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("spreadsheet_id", "gid", "member_key", name="uq_form_point_award_source_member"),
    )
    op.create_index("ix_formpointaward_user_id", "formpointaward", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_formpointaward_user_id", table_name="formpointaward")
    op.drop_table("formpointaward")
