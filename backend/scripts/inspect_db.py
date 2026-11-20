"""Read-only viewer for aml.db.

Usage (from the backend/ folder):
    python scripts/inspect_db.py                      # tables + row counts
    python scripts/inspect_db.py alerts               # first 20 rows of a table
    python scripts/inspect_db.py alerts 50            # first 50 rows
    python scripts/inspect_db.py "SELECT rule_id, COUNT(*) FROM alerts GROUP BY rule_id"
"""

import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "aml.db"
MAX_WIDTH = 60

conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
tables = [
    name for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
]


def show(cursor):
    headers = [d[0] for d in cursor.description]
    rows = [
        [
            (s if len(s) <= MAX_WIDTH else s[:MAX_WIDTH - 3] + "...")
            for s in map(str, row)
        ]
        for row in cursor.fetchall()
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

if not args:
    for t in tables:
        count = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{t}")')]
        print(f"{t:24} {count:>7} rows   columns: {', '.join(cols)}")
elif args[0] in tables:
    limit = int(args[1]) if len(args) > 1 else 20
    show(conn.execute(f'SELECT * FROM "{args[0]}" LIMIT ?', (limit,)))
else:
    show(conn.execute(" ".join(args)))
