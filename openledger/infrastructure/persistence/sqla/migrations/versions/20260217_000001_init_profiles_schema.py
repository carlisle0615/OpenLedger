"""init profiles schema

Revision ID: 20260217_000001
Revises:
Create Date: 2026-02-17 16:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260217_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("period_key", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("period_mode", sa.String(), nullable=True),
        sa.Column("period_day", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.String(), nullable=True),
        sa.Column("period_end", sa.String(), nullable=True),
        sa.Column("period_label", sa.String(), nullable=True),
        sa.Column("cross_month", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.Column("outputs_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "run_id", name="uq_bills_profile_run"),
    )
    op.create_index("idx_bills_profile_period", "bills", ["profile_id", "period_key"], unique=False)
    op.create_table(
        "run_bindings",
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("idx_run_bindings_profile", "run_bindings", ["profile_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_run_bindings_profile", table_name="run_bindings")
    op.drop_table("run_bindings")
    op.drop_index("idx_bills_profile_period", table_name="bills")
    op.drop_table("bills")
    op.drop_table("profiles")
