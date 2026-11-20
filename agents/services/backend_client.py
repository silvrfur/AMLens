from typing import Protocol
from .audit_service import consume
from ..schemas.investigation import AlertBundle

class BackendClient(Protocol):
    def get_alert_context(self, alert_id: str) -> AlertBundle: ...

# INTEGRATION POINT — MEMBER 1 SQLITE BACKEND
# This implementation currently reads the standalone synthetic SQLite database.
# Once Member 1 finalises the shared database schema and backend APIs,
# replace or configure this adapter while preserving the BackendClient interface.
class SQLiteBackendClient:
    def __init__(self, db): self.db = db

    def get_alert_context(self, alert_id: str) -> AlertBundle:
        consume("backend.read")
        with self.db.connect() as c:
            c.execute("BEGIN")
            alert = c.execute("SELECT * FROM alerts WHERE alert_id=?", (alert_id,)).fetchone()
            if alert is None: raise KeyError("Alert not found")
            rows = c.execute("""SELECT * FROM transactions WHERE account_token=(
                SELECT account_token FROM transactions WHERE transaction_id=?) ORDER BY timestamp,transaction_id""",
                (alert['transaction_id'],)).fetchall()
        return AlertBundle.model_validate({"alert": dict(alert), "transactions": [dict(r) for r in rows]})
