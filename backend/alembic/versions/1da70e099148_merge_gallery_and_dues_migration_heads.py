"""merge gallery and dues migration heads

Revision ID: 1da70e099148
Revises: 3d88548564e0, f7a2d5c8b613
Create Date: 2026-09-21 01:13:38.830032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1da70e099148'
down_revision: Union[str, Sequence[str], None] = ('3d88548564e0', 'f7a2d5c8b613')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
