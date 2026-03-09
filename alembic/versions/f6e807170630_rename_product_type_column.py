"""rename product_type column

Revision ID: f6e807170630
Revises: 2e331238d0d1
Create Date: 2026-03-09 16:46:56.780790

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6e807170630'
down_revision: Union[str, Sequence[str], None] = '2e331238d0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("marketplace_listings") as batch_op:
        batch_op.alter_column(
            "product_type",
            new_column_name="marketplace_product_type",
            existing_type=sa.String(length=255),
            nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("marketplace_listings") as batch_op:
        batch_op.alter_column(
            "marketplace_product_type",
            new_column_name="product_type",
            existing_type=sa.String(length=255),
            nullable=True,
        )
