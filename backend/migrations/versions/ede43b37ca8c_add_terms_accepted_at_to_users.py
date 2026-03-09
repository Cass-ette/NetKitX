"""add terms_accepted_at to users

Revision ID: ede43b37ca8c
Revises: f3f5e12ef17e
Create Date: 2026-03-10 03:17:17.814704

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ede43b37ca8c"
down_revision: Union[str, Sequence[str], None] = "f3f5e12ef17e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("terms_accepted_at", sa.TIMESTAMP(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "terms_accepted_at")
