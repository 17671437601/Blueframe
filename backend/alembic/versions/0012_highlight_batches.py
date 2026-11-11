"""Create highlight batches for bulk clip rendering."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0012_highlight_batches"
down_revision: str | None = "0011_diagnostics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "highlight_batches",
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
        "highlight_clips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("output_path", sa.Text()),
        sa.Column("error_summary", sa.String(500)),
        sa.ForeignKeyConstraint(["batch_id"], ["highlight_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["project_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("batch_id", "item_index", name="uq_highlight_batch_clip"),
    )


def downgrade() -> None:
    op.drop_table("highlight_clips")
    op.drop_table("highlight_batches")
