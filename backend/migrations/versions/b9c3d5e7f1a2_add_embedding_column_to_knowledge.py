"""add embedding column to knowledge_entries

Revision ID: b9c3d5e7f1a2
Revises: f1ea177f7f63
Create Date: 2026-03-11 10:00:00.000000
"""

from alembic import op

revision = "b9c3d5e7f1a2"
down_revision = "f1ea177f7f63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE knowledge_entries ADD COLUMN embedding vector(1536)")
    # ivfflat requires rows to exist; use hnsw for zero-row bootstrap
    op.execute(
        "CREATE INDEX ix_knowledge_entries_embedding "
        "ON knowledge_entries USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_entries_embedding")
    op.execute("ALTER TABLE knowledge_entries DROP COLUMN IF EXISTS embedding")
