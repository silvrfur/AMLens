"""Shared test setup.

Database tests run against a real, throwaway PostgreSQL database given by
TEST_DATABASE_URL (its name must contain "test"; it is wiped between tests).
Without TEST_DATABASE_URL they are skipped; pure-Python tests still run.

    $env:TEST_DATABASE_URL = "postgresql+psycopg://amlens:amlens_dev@localhost:5432/amlens_test"
    pytest
"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
# backend/ for `app`, repo root for the agents package (member3-agents layout).
sys.path[:0] = [str(BACKEND), str(BACKEND.parent)]

load_dotenv(BACKEND / '.env')
TEST_DATABASE_URL = os.getenv('TEST_DATABASE_URL')

os.environ.setdefault('TOKEN_SECRET', 'test-secret-should-be-changed-before-prod-123456789')
os.environ.setdefault('AML_SOURCE_TIMEZONE', 'UTC')
if TEST_DATABASE_URL:
    # Point the whole app (and the agent adapter) at the test database.
    os.environ['DATABASE_URL'] = TEST_DATABASE_URL
    os.environ.pop('AML_SOURCE_DATABASE_URL', None)

TABLES = 'transactions, alerts, investigations, investigator_decisions, report_versions, audit_history'


@pytest.fixture(scope='session')
def pg_url():
    if not TEST_DATABASE_URL:
        pytest.skip('TEST_DATABASE_URL not set; skipping PostgreSQL tests')
    from sqlalchemy.engine import make_url
    from app.database.connection import normalize_database_url
    url = normalize_database_url(TEST_DATABASE_URL)
    if 'test' not in (make_url(url).database or ''):
        pytest.exit('TEST_DATABASE_URL database name must contain "test" (it gets wiped)', returncode=2)
    return url


@pytest.fixture(scope='session')
def alembic_cfg(pg_url):
    from app.database.schema_check import alembic_config
    cfg = alembic_config()
    cfg.attributes['database_url'] = pg_url
    return cfg


@pytest.fixture(scope='session')
def migrated_db(alembic_cfg):
    from alembic import command
    command.downgrade(alembic_cfg, 'base')
    command.upgrade(alembic_cfg, 'head')
    return alembic_cfg


@pytest.fixture
def clean_db(migrated_db, tmp_path, monkeypatch):
    """Empty, fully migrated test database; agent runtime SQLite in tmp_path."""
    from alembic import command
    from sqlalchemy import text
    from app.database.connection import engine
    command.upgrade(migrated_db, 'head')  # in case a test downgraded
    with engine.begin() as conn:
        conn.execute(text(f'TRUNCATE {TABLES}'))
    monkeypatch.setenv('AML_AGENT_DATABASE_PATH', str(tmp_path / 'agent_runtime.db'))
    yield engine
