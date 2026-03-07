"""add audit_logs announcements and user quotas

Revision ID: c9080a6e0993
Revises: 05a264c05b59
Create Date: 2026-03-08 01:48:35.511231

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c9080a6e0993"
down_revision: Union[str, Sequence[str], None] = "05a264c05b59"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add quota columns to users
    op.add_column("users", sa.Column("max_concurrent_tasks", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("max_daily_tasks", sa.Integer(), nullable=True))
    op.execute("UPDATE users SET max_concurrent_tasks = 5 WHERE max_concurrent_tasks IS NULL")
    op.execute("UPDATE users SET max_daily_tasks = 100 WHERE max_daily_tasks IS NULL")
    op.alter_column("users", "max_concurrent_tasks", nullable=False, server_default="5")
    op.alter_column("users", "max_daily_tasks", nullable=False, server_default="100")

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # Create announcements table
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="info"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("announcements")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_column("users", "max_daily_tasks")
    op.drop_column("users", "max_concurrent_tasks")
