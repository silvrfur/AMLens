"""Manual smoke check (not a pytest test): build an AlertBundle from the
PostgreSQL source data.

Usage (from backend/, DATABASE_URL set): python test_real_integration.py [ALERT_ID]
"""
import os
import sys

from app.integrations.team_backend import TeamBackend


def main():
    # Reads DATABASE_URL (or AML_SOURCE_DATABASE_URL) from the environment / .env
    backend = TeamBackend(
        source_timezone=os.getenv("AML_SOURCE_TIMEZONE", "UTC")
    )

    # Rapid-movement alert from your previous API test
    alert_id = sys.argv[1] if len(sys.argv) > 1 else "AL_3d8358dcb78db6b328ce_3"

    print("\nTesting real PostgreSQL integration...\n")

    bundle = backend.get_alert_context(alert_id)

    print("Alert ID:", bundle.alert.alert_id)
    print("Typology:", bundle.alert.typology)
    print("Status:", bundle.alert.status)
    print("Transaction Count:", len(bundle.transactions))

    print("\nTransactions:")

    for tx in bundle.transactions:
        print(
            tx.transaction_id,
            "|",
            tx.transaction_type,
            "|",
            tx.amount,
            "|",
            tx.currency
        )

    backend.close()
    print("\nIntegration successful!")


if __name__ == "__main__":
    main()
