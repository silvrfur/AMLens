from ..services.backend_client import SQLiteBackendClient
from .sample_data import seed

class MockBackendClient(SQLiteBackendClient):
    """Uses real SQLite with idempotent synthetic fixtures, not a second data store."""
    def __init__(self, db):
        seed(db)
        super().__init__(db)
