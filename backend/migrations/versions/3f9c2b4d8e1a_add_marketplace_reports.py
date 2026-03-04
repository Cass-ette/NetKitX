"""Add marketplace reports table

Revision ID: 3f9c2b4d8e1a
Revises: 27e85a258187
Create Date: 2026-03-05 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f9c2b4d8e1a"
down_revision: Union[str, None] = "27e85a258187"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add marketplace_reports table."""
    op.create_table(
        "marketplace_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plugin_id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["plugin_id"],
            ["marketplace_plugins.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_reports_plugin", "marketplace_reports", ["plugin_id"])
    op.create_index("idx_reports_status", "marketplace_reports", ["status"])


def downgrade() -> None:
    """Remove marketplace_reports table."""
    op.drop_index("idx_reports_status", table_name="marketplace_reports")
    op.drop_index("idx_reports_plugin", table_name="marketplace_reports")
    op.drop_table("marketplace_reports")
