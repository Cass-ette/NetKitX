"""add_knowledge_tables

Revision ID: fa32867a3dff
Revises: c9080a6e0993
Create Date: 2026-03-08 23:38:07.926277

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fa32867a3dff"
down_revision: Union[str, Sequence[str], None] = "c9080a6e0993"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("agent_mode", sa.String(20), nullable=False),
        sa.Column("security_mode", sa.String(20), nullable=False),
        sa.Column("lang", sa.String(10), nullable=False, server_default="en"),
        sa.Column("total_turns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])

    op.create_table(
        "session_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("action", postgresql.JSONB(), nullable=True),
        sa.Column("action_result", postgresql.JSONB(), nullable=True),
        sa.Column("action_status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_session_turns_session_id", "session_turns", ["session_id"])

    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("agent_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scenario", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("vulnerability_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("tools_used", postgresql.JSONB(), nullable=True),
        sa.Column("attack_chain", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="partial"),
        sa.Column("key_findings", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column("extraction_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_entries_user_id", "knowledge_entries", ["user_id"])
    op.create_index("ix_knowledge_entries_session_id", "knowledge_entries", ["session_id"])

    # Full-text search vector + GIN index (Phase 2/3 will populate)
    op.execute("""
        ALTER TABLE knowledge_entries
        ADD COLUMN search_vector tsvector;
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_entries_search
        ON knowledge_entries USING GIN (search_vector);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("knowledge_entries")
    op.drop_table("session_turns")
    op.drop_table("agent_sessions")
