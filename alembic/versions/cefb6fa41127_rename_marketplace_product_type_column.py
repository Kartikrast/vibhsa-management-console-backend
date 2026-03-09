"""rename marketplace product type column

Revision ID: cefb6fa41127
Revises: 6715f7effe24
Create Date: 2026-03-09 15:13:50.397847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cefb6fa41127'
down_revision: Union[str, Sequence[str], None] = '6715f7effe24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
