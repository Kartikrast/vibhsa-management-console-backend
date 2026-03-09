"""rename marketplace_product_type column

Revision ID: 2e331238d0d1
Revises: cefb6fa41127
Create Date: 2026-03-09 16:44:44.768095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e331238d0d1'
down_revision: Union[str, Sequence[str], None] = 'cefb6fa41127'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
