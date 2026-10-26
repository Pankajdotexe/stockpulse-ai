"""Alembic environment configuration script.

Reads DATABASE_URL dynamically from environment variables or application configuration.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Interpret the config file for Python logging.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for 'autogenerate' support (will be set in later phases when models are added)
target_metadata = None


def get_database_url() -> str:
    """Retrieve database URL from environment or configuration."""
    # First check standard DATABASE_URL environment variable
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    # Fallback to alembic.ini configured url or default dev url
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url:
        return ini_url

    return "postgresql+psycopg://stockpulse:stockpulse_dev_password@localhost:5432/stockpulse_db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
