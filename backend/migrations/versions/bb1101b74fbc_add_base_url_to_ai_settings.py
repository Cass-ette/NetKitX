"""add base_url to ai_settings

Revision ID: bb1101b74fbc
Revises: 5a1c3e7f9b2d
Create Date: 2026-03-07 18:28:02.305669

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "bb1101b74fbc"
down_revision: Union[str, Sequence[str], None] = "5a1c3e7f9b2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_settings", sa.Column("base_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_settings", "base_url")
