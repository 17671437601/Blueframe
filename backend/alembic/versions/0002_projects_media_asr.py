"""Create project, media source, and ASR timeline tables."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_projects_media_asr"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("project_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("output_relative_path", sa.Text(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_updated", "projects", ["updated_at"])
    op.create_table(
        "project_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("modified_ns", sa.BigInteger(), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("media_info_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id", "relative_path", "content_fingerprint",
            name="uq_project_source_identity",
        ),
    )
    op.create_index(
        "ix_project_sources_order", "project_sources", ["project_id", "order_index"]
    )
    op.create_table(
        "asr_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(length=36),
            sa.ForeignKey("project_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cache_key", sa.String(length=256), nullable=False, unique=True),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "asr_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("asr_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_index", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.BigInteger(), nullable=False),
        sa.Column("end_ms", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.UniqueConstraint("document_id", "line_index", name="uq_asr_line_index"),
    )


def downgrade() -> None:
    op.drop_table("asr_lines")
    op.drop_table("asr_documents")
    op.drop_index("ix_project_sources_order", table_name="project_sources")
    op.drop_table("project_sources")
    op.drop_index("ix_projects_updated", table_name="projects")
    op.drop_table("projects")
