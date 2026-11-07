"""Create foundation metadata tables."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schema_metadata",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_table(
        "app_installation",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_table(
        "account_summary",
        sa.Column("user_id", sa.String(length=100), primary_key=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("credential_reference", sa.String(length=500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "entitlement_snapshot",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=100),
            sa.ForeignKey("account_summary.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signed_payload", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("entitlement_snapshot")
    op.drop_table("account_summary")
    op.drop_table("app_installation")
    op.drop_table("schema_metadata")
