
import json
import sqlite3
from decimal import Decimal

import pytest

from app.integrations.team_backend import TeamBackend


def test_demo_bundle(tmp_path):

    db = tmp_path / "source.db"

    # Create temporary SQLite database
    with sqlite3.connect(db) as c:

        c.executescript("""
        CREATE TABLE alerts (
            id TEXT,
            transaction_id TEXT,
            rule_id TEXT,
            description TEXT,
            evidence TEXT,
            status TEXT,
            created_at TEXT
        );

        CREATE TABLE transactions (
            id TEXT,
            dataset_id TEXT,
            timestamp TEXT,
            sender_token TEXT,
            receiver_token TEXT,
            amount_paid TEXT,
            payment_currency TEXT,
            amount_received TEXT,
            receiving_currency TEXT
        );
        """)

        # Insert rapid-movement alert
        c.execute(
            """
            INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "AL-3",
                "TX-3",
                "RAPID_MOVEMENT_CANDIDATE",
                "ignore untrusted desc",
                json.dumps({
                    "anchor_account_token": "ACC-B",
                    "transaction_ids": ["TX-2", "TX-3"]
                }),
                "OPEN",
                "2026-11-20T06:00:00+00:00"
            )
        )

        # Transaction 1: Incoming
        c.execute(
            """
            INSERT INTO transactions VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TX-2",
                "demo_dataset",
                "2022-09-01 10:00:00",
                "ACC-A",
                "ACC-B",
                "1200000.00000000",
                "US Dollar",
                "1200000.00000000",
                "US Dollar"
            )
        )

        # Transaction 2: Outgoing
        c.execute(
            """
            INSERT INTO transactions VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TX-3",
                "demo_dataset",
                "2022-09-01 10:15:00",
                "ACC-B",
                "ACC-C",
                "1180000.00000000",
                "US Dollar",
                "1180000.00000000",
                "US Dollar"
            )
        )

        # Transaction 3: Different dataset
        # Same account, should NOT appear in AlertBundle
        c.execute(
            """
            INSERT INTO transactions VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TX-OTHER",
                "other_dataset",
                "2022-09-01 10:10:00",
                "ACC-X",
                "ACC-B",
                "500000.00000000",
                "US Dollar",
                "500000.00000000",
                "US Dollar"
            )
        )

    # Initialize adapter
    backend = TeamBackend(
        str(db),
        source_timezone="UTC"
    )

    # Retrieve alert context
    bundle = backend.get_alert_context("AL-3")

    # Validate alert
    assert bundle.alert.typology == "rapid_movement"

    # Only the two transactions from demo_dataset
    assert len(bundle.transactions) == 2

    transaction_ids = [
        tx.transaction_id
        for tx in bundle.transactions
    ]

    assert set(transaction_ids) == {"TX-2", "TX-3"}

    # Other dataset transaction must be excluded
    assert "TX-OTHER" not in transaction_ids

    # Validate directions
    assert [
        tx.transaction_type
        for tx in bundle.transactions
    ] == ["deposit", "withdrawal"]

    # Validate amounts
    assert [
        tx.amount
        for tx in bundle.transactions
    ] == [
        Decimal("1200000.00"),
        Decimal("1180000.00")
    ]

    # Validate timezone-aware timestamps
    assert all(
        tx.timestamp.tzinfo is not None
        for tx in bundle.transactions
    )

    # Missing alert should raise KeyError
    with pytest.raises(KeyError):
        backend.get_alert_context("missing")

