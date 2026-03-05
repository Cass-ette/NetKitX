"""add ai_settings table

Revision ID: 5a1c3e7f9b2d
Revises: 3f9c2b4d8e1a
Create Date: 2026-03-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a1c3e7f9b2d"
down_revision: Union[str, None] = "3f9c2b4d8e1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("api_key_enc", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_ai_settings_user_id", "ai_settings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_settings_user_id")
    op.drop_table("ai_settings")
