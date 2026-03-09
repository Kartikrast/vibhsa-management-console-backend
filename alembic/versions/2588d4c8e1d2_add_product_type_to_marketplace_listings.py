"""add product_type to marketplace_listings

Revision ID: 2588d4c8e1d2
Revises: 7cbf80e38ecc
Create Date: 2026-03-09 12:09:59.596034

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2588d4c8e1d2'
down_revision: Union[str, Sequence[str], None] = '7cbf80e38ecc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "marketplace_listings",
        sa.Column("product_type", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("marketplace_listings", "product_type")
