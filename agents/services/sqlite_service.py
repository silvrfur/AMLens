import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
 transaction_id TEXT PRIMARY KEY, account_token TEXT NOT NULL, counterparty_token TEXT NOT NULL,
 amount TEXT NOT NULL, currency TEXT NOT NULL, timestamp TEXT NOT NULL,
 transaction_type TEXT NOT NULL CHECK(transaction_type IN ('deposit','withdrawal')), description TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alerts (
 alert_id TEXT PRIMARY KEY, transaction_id TEXT NOT NULL REFERENCES transactions(transaction_id),
 label TEXT NOT NULL, typology TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS investigations (
 investigation_id TEXT PRIMARY KEY, alert_id TEXT NOT NULL,
 execution_status TEXT NOT NULL, report_json TEXT, verification_json TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 lease_owner TEXT, lease_until REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS agent_runs (
 run_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL REFERENCES investigations(investigation_id),
 agent_name TEXT NOT NULL, execution_status TEXT NOT NULL, started_at TEXT NOT NULL,
 completed_at TEXT, error_message TEXT);
CREATE TABLE IF NOT EXISTS tool_calls (
 call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(run_id), tool_name TEXT NOT NULL,
 input_json TEXT NOT NULL, output_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (
 event_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL REFERENCES investigations(investigation_id),
 event_type TEXT NOT NULL, actor TEXT NOT NULL, timestamp TEXT NOT NULL, details_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS account_history ON transactions(account_token, timestamp);
CREATE INDEX IF NOT EXISTS runs_investigation ON agent_runs(investigation_id);
"""

class SQLiteService:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)

    def connect(self):
        # Context manager below both commits/rolls back AND closes connections.
        return Connection(self.path)

class Connection:
    def __init__(self, path): self.path = path
    def __enter__(self):
        self.c = sqlite3.connect(self.path, timeout=30)
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA foreign_keys=ON")
        return self.c
    def __exit__(self, typ, value, tb):
        try:
            self.c.rollback() if typ else self.c.commit()
        finally:
            self.c.close()
