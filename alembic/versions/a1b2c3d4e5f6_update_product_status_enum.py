"""update product_status_enum: add ACTIVE, ARCHIVED; migrate READY to ACTIVE; remove READY

Revision ID: a1b2c3d4e5f6
Revises: 212a32db07f0
Create Date: 2026-02-17 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '212a32db07f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL requires new enum values to be committed before use,
    # so we skip ADD VALUE and instead recreate the enum type entirely.

    # Step 1: Drop the column default (it depends on the enum type)
    op.execute("ALTER TABLE products ALTER COLUMN status DROP DEFAULT")

    # Step 2: Convert column to text temporarily
    op.execute("ALTER TABLE products ALTER COLUMN status TYPE text USING status::text")

    # Step 3: Drop old enum
    op.execute("DROP TYPE product_status_enum")

    # Step 4: Create new enum with updated values
    op.execute("CREATE TYPE product_status_enum AS ENUM ('DRAFT', 'ACTIVE', 'PUBLISHED', 'ARCHIVED')")

    # Step 5: Migrate READY -> ACTIVE in the text column
    op.execute("UPDATE products SET status = 'ACTIVE' WHERE status = 'READY'")

    # Step 6: Convert column back to enum
    op.execute("ALTER TABLE products ALTER COLUMN status TYPE product_status_enum USING status::product_status_enum")

    # Step 7: Restore default
    op.execute("ALTER TABLE products ALTER COLUMN status SET DEFAULT 'DRAFT'")


def downgrade() -> None:
    # Reverse: recreate old enum, migrate ACTIVE back to READY, drop ARCHIVED
    op.execute("ALTER TABLE products ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE products ALTER COLUMN status TYPE text USING status::text")
    op.execute("DROP TYPE product_status_enum")
    op.execute("CREATE TYPE product_status_enum AS ENUM ('DRAFT', 'READY', 'PUBLISHED')")
    op.execute("UPDATE products SET status = 'READY' WHERE status = 'ACTIVE'")
    op.execute("UPDATE products SET status = 'DRAFT' WHERE status = 'ARCHIVED'")
    op.execute("ALTER TABLE products ALTER COLUMN status TYPE product_status_enum USING status::product_status_enum")
    op.execute("ALTER TABLE products ALTER COLUMN status SET DEFAULT 'DRAFT'")
