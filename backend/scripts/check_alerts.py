"""Check that every stored alert converts into a valid agent AlertBundle.

Usage (from the backend/ folder, venv active):
    python scripts/check_alerts.py                 # all alerts
    python scripts/check_alerts.py a6cd8e166e0bd140f23c   # one dataset
"""

import logging
import sqlite3
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND.parent)]

from app.integrations.team_backend import TeamBackend  # noqa: E402

logging.disable(logging.WARNING)

DB = BACKEND / "aml.db"
dataset = sys.argv[1] if len(sys.argv) > 1 else None

backend = TeamBackend(database_path=str(DB), source_timezone="UTC")

with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as conn:
    alerts = conn.execute(
        "SELECT id, rule_id FROM alerts "
        "WHERE (? IS NULL OR id LIKE 'AL_' || ? || '_%') ORDER BY id",
        (dataset, dataset),
    ).fetchall()

ok = Counter()
failed = []

for alert_id, rule_id in alerts:
    try:
        bundle = backend.get_alert_context(alert_id)
        ok[rule_id] += 1
        print(f"OK    {alert_id:32} {rule_id:26} {len(bundle.transactions)} txns")
    except Exception as exc:
        failed.append(alert_id)
        print(f"FAIL  {alert_id:32} {rule_id:26} {type(exc).__name__}: {exc}")

print(f"\n{sum(ok.values())}/{len(alerts)} alerts OK  {dict(ok)}")
sys.exit(1 if failed else 0)
