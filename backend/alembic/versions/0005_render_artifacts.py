"""Create recoverable render artifact records."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_render_artifacts"
down_revision: str | None = "0004_edit_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "render_artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("working_path", sa.Text(), nullable=False),
        sa.Column("published_path", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_render_artifact_identity", "render_artifacts",
        ["project_id", "plan_id", "spec_hash", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_render_artifact_identity", table_name="render_artifacts")
    op.drop_table("render_artifacts")
