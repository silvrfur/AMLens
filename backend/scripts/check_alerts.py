"""Check that every stored alert converts into a valid agent AlertBundle.

Usage (from the backend/ folder, venv active, DATABASE_URL set):
    python scripts/check_alerts.py                 # all alerts
    python scripts/check_alerts.py a6cd8e166e0bd140f23c   # one dataset

Set AML_SOURCE_TIMEZONE if your source timestamps are not UTC.
"""

import logging
import os
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND.parent)]

from sqlalchemy import text  # noqa: E402

from app.integrations.team_backend import TeamBackend  # noqa: E402

logging.disable(logging.WARNING)

dataset = sys.argv[1] if len(sys.argv) > 1 else None

backend = TeamBackend(source_timezone=os.getenv("AML_SOURCE_TIMEZONE", "UTC"))

with backend._read_only() as conn:
    alerts = conn.execute(
        text(
            "SELECT id, rule_id FROM alerts "
            "WHERE (CAST(:dataset AS text) IS NULL "
            "       OR id LIKE 'AL\\_' || :dataset || '\\_%') "
            "ORDER BY id"
        ),
        {"dataset": dataset},
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

backend.close()
print(f"\n{sum(ok.values())}/{len(alerts)} alerts OK  {dict(ok)}")
sys.exit(1 if failed else 0)
