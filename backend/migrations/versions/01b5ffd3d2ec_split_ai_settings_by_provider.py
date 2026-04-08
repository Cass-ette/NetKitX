"""split_ai_settings_by_provider

Revision ID: 01b5ffd3d2ec
Revises: d1e2f3a4b5c6
Create Date: 2026-04-08 21:56:52.053880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '01b5ffd3d2ec'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - split ai_settings into provider-specific columns."""
    # Add new columns for each provider
    op.add_column('ai_settings', sa.Column('deepseek_api_key_enc', sa.Text(), nullable=True))
    op.add_column('ai_settings', sa.Column('deepseek_model', sa.String(length=100), nullable=True))
    op.add_column('ai_settings', sa.Column('glm_api_key_enc', sa.Text(), nullable=True))
    op.add_column('ai_settings', sa.Column('glm_model', sa.String(length=100), nullable=True))
    op.add_column('ai_settings', sa.Column('custom_api_key_enc', sa.Text(), nullable=True))
    op.add_column('ai_settings', sa.Column('custom_model', sa.String(length=100), nullable=True))
    # Rename base_url to custom_base_url for clarity
    op.alter_column('ai_settings', 'base_url', new_column_name='custom_base_url')

    # Migrate existing data
    op.execute("""
        UPDATE ai_settings
        SET
            deepseek_api_key_enc = CASE WHEN provider = 'deepseek' THEN api_key_enc ELSE NULL END,
            deepseek_model = CASE WHEN provider = 'deepseek' THEN model ELSE NULL END,
            glm_api_key_enc = CASE WHEN provider = 'glm' THEN api_key_enc ELSE NULL END,
            glm_model = CASE WHEN provider = 'glm' THEN model ELSE NULL END,
            custom_api_key_enc = CASE WHEN provider = 'custom' THEN api_key_enc ELSE NULL END,
            custom_model = CASE WHEN provider = 'custom' THEN model ELSE NULL END
    """)

    # Make provider nullable for default
    op.alter_column('ai_settings', 'provider', nullable=True, existing_type=sa.String(length=20))

    # Set default values for models
    op.execute("""
        UPDATE ai_settings
        SET
            deepseek_model = COALESCE(deepseek_model, 'deepseek-chat'),
            glm_model = COALESCE(glm_model, 'glm-4-flash')
    """)

    # Drop old columns
    op.drop_column('ai_settings', 'api_key_enc')
    op.drop_column('ai_settings', 'model')


def downgrade() -> None:
    """Downgrade schema - merge back to single provider config."""
    # Add back old columns
    op.add_column('ai_settings', sa.Column('api_key_enc', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('ai_settings', sa.Column('model', sa.VARCHAR(length=100), autoincrement=False, nullable=True))

    # Migrate data back
    op.execute("""
        UPDATE ai_settings
        SET
            api_key_enc = CASE
                WHEN provider = 'deepseek' THEN deepseek_api_key_enc
                WHEN provider = 'glm' THEN glm_api_key_enc
                WHEN provider = 'custom' THEN custom_api_key_enc
                ELSE deepseek_api_key_enc
            END,
            model = CASE
                WHEN provider = 'deepseek' THEN deepseek_model
                WHEN provider = 'glm' THEN glm_model
                WHEN provider = 'custom' THEN custom_model
                ELSE deepseek_model
            END
    """)

    # Make columns non-nullable again
    op.alter_column('ai_settings', 'api_key_enc', nullable=False)
    op.alter_column('ai_settings', 'model', nullable=False)
    op.alter_column('ai_settings', 'provider', nullable=False)

    # Rename back
    op.alter_column('ai_settings', 'custom_base_url', new_column_name='base_url')

    # Drop new columns
    op.drop_column('ai_settings', 'deepseek_api_key_enc')
    op.drop_column('ai_settings', 'deepseek_model')
    op.drop_column('ai_settings', 'glm_api_key_enc')
    op.drop_column('ai_settings', 'glm_model')
    op.drop_column('ai_settings', 'custom_api_key_enc')
    op.drop_column('ai_settings', 'custom_model')
