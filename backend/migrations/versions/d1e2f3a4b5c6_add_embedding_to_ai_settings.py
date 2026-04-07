"""Add embedding columns to ai_settings

Revision ID: d1e2f3a4b5c6
Revises: c4d8e9f1a2b3
Create Date: 2026-03-13 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c4d8e9f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_settings", sa.Column("embedding_provider", sa.String(20), nullable=True))
    op.add_column("ai_settings", sa.Column("embedding_api_key_enc", sa.Text(), nullable=True))
    op.add_column("ai_settings", sa.Column("embedding_model", sa.String(100), nullable=True))

    # Migrate .env RAG_EMBEDDING_* config to admin user (user_id=1) if configured
    try:
        from app.core.config import settings
        from app.services.ai_service import encrypt_key

        if settings.RAG_EMBEDDING_API_KEY and settings.RAG_EMBEDDING_PROVIDER:
            encrypted = encrypt_key(settings.RAG_EMBEDDING_API_KEY)
            provider = settings.RAG_EMBEDDING_PROVIDER
            model = settings.RAG_EMBEDDING_MODEL or "embedding-3"

            # Only update if admin user has an ai_settings row
            op.execute(
                sa.text(
                    """
                    UPDATE ai_settings
                    SET embedding_provider = :provider,
                        embedding_api_key_enc = :enc,
                        embedding_model = :model
                    WHERE user_id = 1
                      AND embedding_api_key_enc IS NULL
                    """
                ).bindparams(provider=provider, enc=encrypted, model=model)
            )
    except Exception:
        # Non-fatal: if .env has no RAG key or import fails, just skip migration
        pass


def downgrade() -> None:
    op.drop_column("ai_settings", "embedding_model")
    op.drop_column("ai_settings", "embedding_api_key_enc")
    op.drop_column("ai_settings", "embedding_provider")
