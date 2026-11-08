"""Create versioned commentary scripts."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006_commentary_scripts"
down_revision: str | None = "0005_render_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commentary_script_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("voice", sa.String(length=200), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("sentences_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "version", name="uq_commentary_script_version"),
    )
    op.create_index("ix_commentary_project_created", "commentary_script_versions", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_commentary_project_created", table_name="commentary_script_versions")
    op.drop_table("commentary_script_versions")
