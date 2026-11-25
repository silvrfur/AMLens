from datetime import datetime, timezone


def utcnow():
    """UTC timestamp as text, in the format SQLite's datetime('now') produces.

    Generated in Python so the same SQL works on SQLite and PostgreSQL.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
