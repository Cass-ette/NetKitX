"""add github_id and avatar_url to users

Revision ID: 05a264c05b59
Revises: bb1101b74fbc
Create Date: 2026-03-07 23:06:22.663368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '05a264c05b59'
down_revision: Union[str, Sequence[str], None] = 'bb1101b74fbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add github_id and avatar_url columns to users table
    op.add_column('users', sa.Column('github_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(length=500), nullable=True))
    op.create_unique_constraint('users_github_id_key', 'users', ['github_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('users_github_id_key', 'users', type_='unique')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'github_id')
