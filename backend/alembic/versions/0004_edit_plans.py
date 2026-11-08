"""Create versioned edit plans."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_edit_plans"
down_revision: str | None = "0003_story_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edit_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "version", name="uq_edit_plan_version"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_edit_plan_idempotency"),
    )
    op.create_index("ix_edit_plans_project", "edit_plans", ["project_id", "version"])


def downgrade() -> None:
    op.drop_index("ix_edit_plans_project", table_name="edit_plans")
    op.drop_table("edit_plans")
