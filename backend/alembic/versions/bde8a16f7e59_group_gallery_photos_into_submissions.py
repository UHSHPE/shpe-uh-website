"""group gallery photos into submissions

Revision ID: bde8a16f7e59
Revises: 1da70e099148
Create Date: 2026-10-21 17:56:18.987565

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "bde8a16f7e59"
down_revision: str | Sequence[str] | None = "1da70e099148"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gallerysubmission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_gallerysubmission_submitted_at"),
        "gallerysubmission",
        ["submitted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_gallerysubmission_submitted_by_user_id"),
        "gallerysubmission",
        ["submitted_by_user_id"],
        unique=False,
    )
    op.add_column(
        "galleryphoto", sa.Column("submission_id", sa.Integer(), nullable=True)
    )

    # Existing photos predate batches. Preserve them as one-photo submissions;
    # matching IDs make the backfill deterministic without application models.
    op.execute(
        """
        INSERT INTO gallerysubmission (id, submitted_by_user_id, submitted_at)
        SELECT id, submitted_by_user_id, submitted_at
        FROM galleryphoto
        """
    )
    op.execute("UPDATE galleryphoto SET submission_id = id")
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('gallerysubmission', 'id'),
            COALESCE((SELECT MAX(id) FROM gallerysubmission), 1),
            EXISTS(SELECT 1 FROM gallerysubmission)
        )
        """
    )

    op.alter_column("galleryphoto", "submission_id", nullable=False)
    op.create_index(
        op.f("ix_galleryphoto_submission_id"),
        "galleryphoto",
        ["submission_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_galleryphoto_submission_id_gallerysubmission",
        "galleryphoto",
        "gallerysubmission",
        ["submission_id"],
        ["id"],
    )
    op.drop_constraint(
        op.f("galleryphoto_submitted_by_user_id_fkey"),
        "galleryphoto",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_galleryphoto_submitted_by_user_id"), table_name="galleryphoto"
    )
    op.drop_column("galleryphoto", "submitted_by_user_id")
    op.drop_column("galleryphoto", "submitted_at")


def downgrade() -> None:
    op.add_column(
        "galleryphoto", sa.Column("submitted_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "galleryphoto", sa.Column("submitted_by_user_id", sa.Integer(), nullable=True)
    )
    op.execute(
        """
        UPDATE galleryphoto AS photo
        SET submitted_by_user_id = submission.submitted_by_user_id,
            submitted_at = submission.submitted_at
        FROM gallerysubmission AS submission
        WHERE photo.submission_id = submission.id
        """
    )
    op.alter_column("galleryphoto", "submitted_at", nullable=False)
    op.alter_column("galleryphoto", "submitted_by_user_id", nullable=False)
    op.create_foreign_key(
        op.f("galleryphoto_submitted_by_user_id_fkey"),
        "galleryphoto",
        "user",
        ["submitted_by_user_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_galleryphoto_submitted_by_user_id"),
        "galleryphoto",
        ["submitted_by_user_id"],
        unique=False,
    )
    op.drop_constraint(
        "fk_galleryphoto_submission_id_gallerysubmission",
        "galleryphoto",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_galleryphoto_submission_id"), table_name="galleryphoto")
    op.drop_column("galleryphoto", "submission_id")
    op.drop_index(
        op.f("ix_gallerysubmission_submitted_by_user_id"),
        table_name="gallerysubmission",
    )
    op.drop_index(
        op.f("ix_gallerysubmission_submitted_at"),
        table_name="gallerysubmission",
    )
    op.drop_table("gallerysubmission")
