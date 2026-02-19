"""sync product_media columns with updated model

Revision ID: b3c4d5e6f7a8
Revises: 212a32db07f0
Create Date: 2026-02-17 21:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add product_id column (nullable FK to products)
    op.add_column('product_media', sa.Column(
        'product_id', UUID(as_uuid=True), nullable=True,
    ))
    op.create_foreign_key(
        'fk_product_media_product_id',
        'product_media', 'products',
        ['product_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_index('ix_product_media_product_id', 'product_media', ['product_id'])

    # 2. Rename file_url -> media_url
    op.alter_column('product_media', 'file_url', new_column_name='media_url')

    # 3. Rename sort_order -> display_order
    op.alter_column('product_media', 'sort_order', new_column_name='display_order')

    # 4. Change media_type from enum to varchar
    #    Convert column to text first, drop enum, then set to varchar
    op.execute("ALTER TABLE product_media ALTER COLUMN media_type TYPE varchar(20) USING media_type::text")
    op.execute("UPDATE product_media SET media_type = LOWER(media_type)")
    op.execute("DROP TYPE IF EXISTS media_type_enum")

    # 5. Make product_variant_id nullable (model allows None)
    op.alter_column('product_media', 'product_variant_id', nullable=True)


def downgrade() -> None:
    # 5. Revert product_variant_id to non-nullable
    op.alter_column('product_media', 'product_variant_id', nullable=False)

    # 4. Recreate enum and convert back
    op.execute("CREATE TYPE media_type_enum AS ENUM ('IMAGE', 'VIDEO')")
    op.execute("UPDATE product_media SET media_type = UPPER(media_type)")
    op.execute("ALTER TABLE product_media ALTER COLUMN media_type TYPE media_type_enum USING media_type::media_type_enum")

    # 3. Rename display_order -> sort_order
    op.alter_column('product_media', 'display_order', new_column_name='sort_order')

    # 2. Rename media_url -> file_url
    op.alter_column('product_media', 'media_url', new_column_name='file_url')

    # 1. Drop product_id column
    op.drop_index('ix_product_media_product_id', table_name='product_media')
    op.drop_constraint('fk_product_media_product_id', 'product_media', type_='foreignkey')
    op.drop_column('product_media', 'product_id')
