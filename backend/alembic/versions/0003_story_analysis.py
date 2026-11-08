"""Create versioned story analysis storage."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_story_analysis"
down_revision: str | None = "0002_projects_media_asr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "story_analysis_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("analysis_json", sa.Text(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "version", name="uq_story_analysis_version"),
    )
    op.create_index(
        "ix_story_analysis_project_created",
        "story_analysis_versions",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_story_analysis_project_created", table_name="story_analysis_versions"
    )
    op.drop_table("story_analysis_versions")
