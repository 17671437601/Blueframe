"""Create story batches for long-form main-plot rendering."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0013_story_batches"
down_revision: str | None = "0012_highlight_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "story_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("analysis_version_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("min_duration_ms", sa.Integer(), nullable=False),
        sa.Column("max_duration_ms", sa.Integer(), nullable=False),
        sa.Column("burn_subtitles", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "story_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("target_duration_ms", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(36)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("output_path", sa.Text()),
        sa.Column("error_summary", sa.String(500)),
        sa.ForeignKeyConstraint(["batch_id"], ["story_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["edit_plans.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("batch_id", "item_index", name="uq_story_batch_item"),
    )


def downgrade() -> None:
    op.drop_table("story_items")
    op.drop_table("story_batches")
