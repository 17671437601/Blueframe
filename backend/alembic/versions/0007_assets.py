"""Create licensed asset catalog."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0007_assets"
down_revision: str | None = "0006_commentary_scripts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("asset_type", sa.String(20), nullable=False), sa.Column("path", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(500), nullable=False), sa.Column("license_name", sa.String(500), nullable=False),
        sa.Column("ownership", sa.String(20), nullable=False), sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assets_type_available", "assets", ["asset_type", "available"])


def downgrade() -> None:
    op.drop_index("ix_assets_type_available", table_name="assets"); op.drop_table("assets")
