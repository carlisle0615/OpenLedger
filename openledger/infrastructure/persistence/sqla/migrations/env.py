from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from openledger.infrastructure.persistence.sqla.models import metadata

config = context.config  # pylint: disable=no-member

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _resolve_db_url() -> str:
    configured = str(os.environ.get("OPENLEDGER_PROFILES_DB_PATH", "") or "").strip()
    if configured:
        p = Path(configured)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return f"sqlite+pysqlite:///{p}"
    return str(config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    url = _resolve_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _resolve_db_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
