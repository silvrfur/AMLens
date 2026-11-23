"""One-time copy of the legacy SQLite aml.db into the PostgreSQL database.

Usage (from the backend/ folder, venv active, DATABASE_URL set):
    alembic upgrade head
    python scripts/migrate_sqlite_to_postgres.py                # copies ./aml.db
    python scripts/migrate_sqlite_to_postgres.py path/to/aml.db

- The SQLite file is opened read-only and never modified.
- IDs are copied unchanged, so alert/transaction/investigation links and
  account tokens stay valid (keep using the same TOKEN_SECRET for new uploads).
- Refuses to run if any target table already has rows.
- Everything is copied in ONE transaction: on any error nothing is written.
- Afterwards, row counts are compared table by table.
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import func, select  # noqa: E402

from app.database.connection import Base, engine  # noqa: E402
from app.database import tables  # noqa: E402,F401
from app.database.schema_check import assert_schema_current  # noqa: E402

# Parents before children (foreign keys).
ORDER = ['transactions', 'alerts', 'investigations',
         'investigator_decisions', 'report_versions', 'audit_history']
CHUNK = 5000


def _dt(value, *, aware: bool):
    if value is None:
        return None
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if aware and dt.tzinfo is None:
        # The old app always generated these with datetime.now(timezone.utc);
        # SQLite dropped the offset when storing them.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _decimal(value):
    # SQLite stored most amounts as REAL; str() gives the shortest exact
    # round-trip text, avoiding binary-float artefacts in NUMERIC.
    return None if value is None else Decimal(str(value))


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def convert(table, row: dict) -> dict:
    out = {}
    for col in table.columns:
        if col.name not in row:
            continue
        value = row[col.name]
        type_name = type(col.type).__name__
        if type_name == 'DateTime':
            out[col.name] = _dt(value, aware=bool(col.type.timezone))
        elif type_name == 'Numeric':
            out[col.name] = _decimal(value)
        elif type_name == 'JSONB':
            out[col.name] = _json(value)
        else:
            out[col.name] = value
    return out


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else BACKEND / 'aml.db').resolve()
    if not source.is_file():
        sys.exit(f'SQLite file not found: {source}')

    assert_schema_current(engine)
    src = sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True)
    src.row_factory = sqlite3.Row
    src_tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    print(f'Source: {source}')
    print(f'Target: {engine.url.render_as_string(hide_password=True)}\n')

    with engine.begin() as dst:
        for name in ORDER:
            if dst.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar():
                sys.exit(f'Target table "{name}" is not empty; refusing to copy. Nothing was written.')

        for name in ORDER:
            table = Base.metadata.tables[name]
            if name not in src_tables:
                print(f'{name:24} not in source, skipped')
                continue
            cursor = src.execute(f'SELECT * FROM "{name}"')
            copied = 0
            while batch := cursor.fetchmany(CHUNK):
                dst.execute(table.insert(), [convert(table, dict(r)) for r in batch])
                copied += len(batch)
            print(f'{name:24} {copied:>8} rows copied')

        print('\nVerifying row counts...')
        ok = True
        for name in ORDER:
            if name not in src_tables:
                continue
            a = src.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            b = dst.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar()
            ok &= a == b
            print(f'{name:24} sqlite={a:<8} postgres={b:<8} {"OK" if a == b else "MISMATCH"}')
        if not ok:
            raise SystemExit('Row count mismatch; transaction rolled back, nothing was written.')

    src.close()
    print('\nDone. The SQLite file was not modified; keep it as a backup.')


if __name__ == '__main__':
    main()
