"""Store privacy-safe structured diagnostic metrics."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0011_diagnostics"
down_revision: str | None = "0010_legacy_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("units", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_diagnostic_metrics_created_at", "diagnostic_metrics", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_diagnostic_metrics_created_at", table_name="diagnostic_metrics")
    op.drop_table("diagnostic_metrics")
