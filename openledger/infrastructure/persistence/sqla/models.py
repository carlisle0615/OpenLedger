from __future__ import annotations

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

profiles = Table(
    "profiles",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("created_at", String),
    Column("updated_at", String),
)

bills = Table(
    "bills",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("profile_id", String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", String, nullable=False),
    Column("period_key", String),
    Column("year", Integer),
    Column("month", Integer),
    Column("period_mode", String),
    Column("period_day", Integer),
    Column("period_start", String),
    Column("period_end", String),
    Column("period_label", String),
    Column("cross_month", Integer),
    Column("created_at", String),
    Column("updated_at", String),
    Column("outputs_json", Text),
    UniqueConstraint("profile_id", "run_id", name="uq_bills_profile_run"),
)

run_bindings = Table(
    "run_bindings",
    metadata,
    Column("run_id", String, primary_key=True),
    Column("profile_id", String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", String),
    Column("updated_at", String),
)

Index("idx_bills_profile_period", bills.c.profile_id, bills.c.period_key)
Index("idx_run_bindings_profile", run_bindings.c.profile_id)
