
from app.integrations.team_backend import TeamBackend

# Connect to your existing SQLite database
backend = TeamBackend(
    database_path="aml.db",
    source_timezone="UTC"
)

# Rapid-movement alert from your previous API test
alert_id = "AL_3d8358dcb78db6b328ce_3"

print("\nTesting real SQLite integration...\n")

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

print("\nIntegration successful!")
