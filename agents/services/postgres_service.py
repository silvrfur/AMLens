"""PostgreSQL store for the agents' runtime data (reports, agent runs, tool calls, audit).

Drop-in alternative to SQLiteService for deployments where the container disk is
ephemeral or more than one replica runs. Tables live in their own schema
(agent_runtime) so they never collide with the backend's tables of the same name
(e.g. `investigations`) when both share one database.

Call sites write SQL with `?` placeholders (SQLite style); the connection wrapper
converts them to psycopg's `%s`. None of the agents' SQL contains a literal `?`.
"""
import psycopg
from psycopg.rows import dict_row

SCHEMA_NAME = "agent_runtime"

# URLs whose schema has been created by this process (the backend builds a store per request).
_READY: set[str] = set()

SCHEMA = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};
SET search_path TO {SCHEMA_NAME};
CREATE TABLE IF NOT EXISTS investigations (
 investigation_id TEXT PRIMARY KEY, alert_id TEXT NOT NULL,
 execution_status TEXT NOT NULL, report_json TEXT, verification_json TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 lease_owner TEXT, lease_until DOUBLE PRECISION NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS agent_runs (
 seq BIGINT GENERATED ALWAYS AS IDENTITY,
 run_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL REFERENCES investigations(investigation_id),
 agent_name TEXT NOT NULL, execution_status TEXT NOT NULL, started_at TEXT NOT NULL,
 completed_at TEXT, error_message TEXT);
CREATE TABLE IF NOT EXISTS tool_calls (
 seq BIGINT GENERATED ALWAYS AS IDENTITY,
 call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(run_id), tool_name TEXT NOT NULL,
 input_json TEXT NOT NULL, output_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (
 seq BIGINT GENERATED ALWAYS AS IDENTITY,
 event_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL REFERENCES investigations(investigation_id),
 event_type TEXT NOT NULL, actor TEXT NOT NULL, timestamp TEXT NOT NULL, details_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS runs_investigation ON agent_runs(investigation_id);
CREATE INDEX IF NOT EXISTS audit_investigation ON audit_log(investigation_id);
"""


def normalize_url(url: str) -> str:
    """Accept SQLAlchemy-style URLs (postgresql+psycopg://) as well as plain libpq ones."""
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


class PostgresService:
    # Column that preserves insertion order (SQLite uses its implicit rowid).
    order_column = "seq"

    def __init__(self, url):
        self.url = normalize_url(url)
        if self.url not in _READY:
            with psycopg.connect(self.url, autocommit=False) as c:
                # Serialise schema creation so replicas starting together don't race.
                c.execute("SELECT pg_advisory_xact_lock(hashtext('agent_runtime_schema'))")
                c.execute(SCHEMA)
            _READY.add(self.url)

    def connect(self):
        return Connection(self.url)

    def begin_write(self, c, lock_key=None):
        """Serialise writers for one investigation (SQLite gets this from BEGIN IMMEDIATE)."""
        if lock_key is not None:
            c.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (lock_key,))


class _Wrapped:
    def __init__(self, conn): self.conn = conn
    def execute(self, sql, params=()):
        return self.conn.execute(sql.replace("?", "%s"), params)


class Connection:
    """Same contract as sqlite_service.Connection: commit on success, roll back on error, always close."""
    def __init__(self, url): self.url = url
    def __enter__(self):
        self.c = psycopg.connect(self.url, row_factory=dict_row, autocommit=False,
                                 options=f"-c search_path={SCHEMA_NAME}")
        return _Wrapped(self.c)
    def __exit__(self, typ, value, tb):
        try:
            self.c.rollback() if typ else self.c.commit()
        finally:
            self.c.close()
