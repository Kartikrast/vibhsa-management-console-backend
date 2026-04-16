"""add walmart webhook tables

Revision ID: a8b9c0d1e2f3
Revises: 79783539640e
Create Date: 2026-04-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "79783539640e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "walmart_webhook_subscriptions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("marketplace_account_id", sa.UUID(as_uuid=True), sa.ForeignKey("marketplace_accounts.id"), nullable=False),
        sa.Column("external_subscription_id", sa.String(255), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_version", sa.String(10), nullable=False, server_default="V1"),
        sa.Column("resource_name", sa.String(50), nullable=False),
        sa.Column("event_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "walmart_webhook_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("event_version", sa.String(10), nullable=False, server_default="V1"),
        sa.Column("resource_name", sa.String(50), nullable=False, index=True),
        sa.Column("payload", postgresql.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="RECEIVED"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("walmart_webhook_events")
    op.drop_table("walmart_webhook_subscriptions")
