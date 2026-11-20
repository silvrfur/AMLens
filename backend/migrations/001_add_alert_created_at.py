import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "aml.db"

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"Database not found: {DB_PATH}"
    )

conn = sqlite3.connect(DB_PATH)

try:
    columns = [
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(alerts)"
        )
    ]

    if "created_at" not in columns:
        conn.execute(
            "ALTER TABLE alerts "
            "ADD COLUMN created_at DATETIME"
        )
        print("Migration successful!")
    else:
        print("Column already exists.")

    conn.commit()

finally:
    conn.close()