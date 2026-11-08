"""Create durable live recording intent and segments."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0009_live_recordings"
down_revision: str | None = "0008_variant_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("recording_sessions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False), sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False), sa.Column("authorization_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("intent_active", sa.Boolean(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("process_id", sa.Integer()), sa.Column("reconnect_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(500)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_table("recording_segments",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"), sa.Column("fingerprint", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["recording_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_recording_segment_sequence"),
    )


def downgrade() -> None:
    op.drop_table("recording_segments"); op.drop_table("recording_sessions")
