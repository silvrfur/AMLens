"""Alembic migrations apply, roll back, and match the ORM models."""
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

EXPECTED = {'transactions', 'alerts', 'investigations',
            'investigator_decisions', 'report_versions', 'audit_history'}


def test_upgrade_downgrade_roundtrip(clean_db, migrated_db):
    command.downgrade(migrated_db, 'base')
    assert not EXPECTED & set(inspect(clean_db).get_table_names())
    command.upgrade(migrated_db, 'head')
    assert EXPECTED <= set(inspect(clean_db).get_table_names())


def test_models_match_migrations(clean_db):
    from app.database.connection import Base
    from app.database import tables  # noqa: F401
    with clean_db.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={'compare_type': True}), Base.metadata)
    assert diff == [], diff


def test_app_refuses_unmigrated_database(clean_db, migrated_db):
    import pytest
    from app.database.schema_check import assert_schema_current
    command.downgrade(migrated_db, 'base')
    try:
        with pytest.raises(RuntimeError, match='alembic upgrade head'):
            assert_schema_current(clean_db)
    finally:
        command.upgrade(migrated_db, 'head')
