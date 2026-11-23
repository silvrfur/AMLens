"""Read-only viewer for the main AML PostgreSQL database.

Usage (from the backend/ folder, venv active, DATABASE_URL set):
    python scripts/inspect_db.py                      # tables + row counts
    python scripts/inspect_db.py alerts               # first 20 rows of a table
    python scripts/inspect_db.py alerts 50            # first 50 rows
    python scripts/inspect_db.py "SELECT rule_id, COUNT(*) FROM alerts GROUP BY rule_id"

Every query runs in a READ ONLY transaction, so it cannot change data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database.connection import engine  # noqa: E402

MAX_WIDTH = 60


def show(result):
    headers = list(result.keys())
    rows = [
        [
            (s if len(s) <= MAX_WIDTH else s[:MAX_WIDTH - 3] + "...")
            for s in map(str, row)
        ]
        for row in result.fetchall()
    ]
    widths = [
        max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
        for i, h in enumerate(headers)
    ]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)))
    print(f"\n({len(rows)} rows)")


args = sys.argv[1:]

with engine.connect() as conn, conn.begin():
    conn.execute(text("SET TRANSACTION READ ONLY"))
    tables = [
        name for (name,) in conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        ))
    ]

    if not args:
        for t in tables:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            cols = [c for (c,) in conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = :t "
                "ORDER BY ordinal_position"), {"t": t})]
            print(f"{t:24} {count:>7} rows   columns: {', '.join(cols)}")
    elif args[0] in tables:
        limit = int(args[1]) if len(args) > 1 else 20
        show(conn.execute(text(f'SELECT * FROM "{args[0]}" LIMIT :n'), {"n": limit}))
    else:
        show(conn.execute(text(" ".join(args))))
