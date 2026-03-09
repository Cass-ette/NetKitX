"""add authorized_targets table

Revision ID: f1ea177f7f63
Revises: ede43b37ca8c
Create Date: 2026-03-10 03:24:01.022844

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1ea177f7f63"
down_revision: Union[str, Sequence[str], None] = "ede43b37ca8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "authorized_targets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_value", sa.String(length=500), nullable=False),
        sa.Column("declaration", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_type", "target_value", name="uq_user_target"),
    )
    op.create_index("ix_authorized_targets_user_id", "authorized_targets", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_authorized_targets_user_id", table_name="authorized_targets")
    op.drop_table("authorized_targets")
