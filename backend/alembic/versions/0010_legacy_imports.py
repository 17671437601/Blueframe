"""Record idempotent legacy imports."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0010_legacy_imports"
down_revision: str | None = "0009_live_recordings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("legacy_imports",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("legacy_table", sa.String(100), nullable=False), sa.Column("legacy_id", sa.String(200), nullable=False),
        sa.Column("new_project_id", sa.String(36), nullable=False), sa.Column("migration_version", sa.String(50), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["new_project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("source_hash", "legacy_table", "legacy_id", name="uq_legacy_import_identity"),
    )


def downgrade() -> None: op.drop_table("legacy_imports")
