from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from core.db.sqlalchemy.models import classroom as classroom_model  # noqa: F401
from core.db.sqlalchemy.models import (
    classroom_material as classroom_material_model,  # noqa: F401
)
from core.db.sqlalchemy.models import file as file_model  # noqa: F401
from core.db.sqlalchemy.models import (
    organization as organization_model,  # noqa: F401
)
from core.db.sqlalchemy.models import user as user_model  # noqa: F401
from core.db.sqlalchemy.models.base import metadata

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)


target_metadata = metadata

VALID_ENVIRONMENTS = {"local", "dev", "test", "prod"}


class DryRunRollback(Exception):
    pass


def get_x_argument(name: str) -> str | None:
    for argument in context.get_x_argument():
        if argument.startswith(f"{name}="):
            return argument.split("=", 1)[1]

    return None


def configure_runtime_environment() -> None:
    selected_environment = get_x_argument("env")
    if selected_environment is None:
        return

    if selected_environment not in VALID_ENVIRONMENTS:
        available = ", ".join(sorted(VALID_ENVIRONMENTS))
        msg = (
            "Unsupported migration environment: "
            f"{selected_environment}. Expected one of: {available}"
        )
        raise ValueError(msg)

    os.environ["ENV"] = selected_environment
    os.environ["ENVIRONMENT"] = selected_environment


def is_dry_run_requested() -> bool:
    return "dry-run" in context.get_x_argument()


def configure_database_url() -> None:
    from core.config import config

    alembic_config.set_main_option("sqlalchemy.url", config.DATABASE_URL)


configure_runtime_environment()
configure_database_url()


def run_migrations_offline() -> None:
    context.configure(
        url=alembic_config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

        if is_dry_run_requested():
            raise DryRunRollback


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        try:
            await connection.run_sync(do_run_migrations)
        except DryRunRollback:
            pass

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
