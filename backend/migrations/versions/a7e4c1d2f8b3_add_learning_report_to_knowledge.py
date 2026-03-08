"""add_learning_report_to_knowledge

Revision ID: a7e4c1d2f8b3
Revises: fa32867a3dff
Create Date: 2026-03-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7e4c1d2f8b3"
down_revision: Union[str, Sequence[str], None] = "fa32867a3dff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add learning_report column to knowledge_entries."""
    op.add_column(
        "knowledge_entries",
        sa.Column("learning_report", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Remove learning_report column."""
    op.drop_column("knowledge_entries", "learning_report")
