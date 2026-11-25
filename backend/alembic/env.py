"""Alembic environment for the main AML PostgreSQL database."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.database.connection import Base, database_url
from app.database import tables  # noqa: F401  (registers ORM models)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    # Tests / tooling may pass an explicit URL; otherwise use DATABASE_URL.
    return config.attributes.get('database_url') or database_url()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata,
                      literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_url(), poolclass=pool.NullPool,
                                connect_args={'connect_timeout': 10})
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
