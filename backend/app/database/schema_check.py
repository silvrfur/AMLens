"""Startup guard: refuse to serve requests against an un-migrated database.

Tables are created and changed only by Alembic (`alembic upgrade head`),
never by the application at runtime.
"""
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / 'alembic.ini'))
    cfg.set_main_option('script_location', str(BACKEND_DIR / 'alembic'))
    return cfg


def assert_schema_current(engine: Engine) -> None:
    heads = set(ScriptDirectory.from_config(alembic_config()).get_heads())
    with engine.connect() as conn:
        current = set(MigrationContext.configure(conn).get_current_heads())
    if current != heads:
        raise RuntimeError(
            f'Database schema is not up to date (database: {sorted(current) or "empty"}, '
            f'code: {sorted(heads)}). Run `alembic upgrade head` from the backend/ folder.')
