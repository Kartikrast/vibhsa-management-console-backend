"""add product_type column to products and marketplace_listings

Revision ID: c1d2e3f4a5b6
Revises: 7cbf80e38ecc
Create Date: 2026-03-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = '7cbf80e38ecc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('product_type', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'product_type')
