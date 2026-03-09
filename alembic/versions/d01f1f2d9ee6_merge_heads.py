"""merge heads

Revision ID: d01f1f2d9ee6
Revises: 2588d4c8e1d2, c1d2e3f4a5b6
Create Date: 2026-03-09 12:18:41.428727

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd01f1f2d9ee6'
down_revision: Union[str, Sequence[str], None] = ('2588d4c8e1d2', 'c1d2e3f4a5b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
