"""Create recoverable variant batches."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0008_variant_batches"
down_revision: str | None = "0007_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("variant_batches",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["project_sources.id"], ondelete="RESTRICT"),
    )
    op.create_table("variant_items",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False), sa.Column("recipe_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("output_path", sa.Text()), sa.Column("error_summary", sa.String(500)),
        sa.ForeignKeyConstraint(["batch_id"], ["variant_batches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("batch_id", "item_index", name="uq_variant_batch_item"),
    )


def downgrade() -> None:
    op.drop_table("variant_items"); op.drop_table("variant_batches")
