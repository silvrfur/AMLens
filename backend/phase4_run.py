
"""
Phase 4: Run real Member 1 PostgreSQL evidence
through the five LangGraph investigation agents.

Uses mock LLM and mock RAG.
Does not modify Member 1's source database (reads are READ ONLY).
Agent results go to the separate agent_runtime.db SQLite file.

Usage (from backend/, DATABASE_URL set):
    python phase4_run.py [ALERT_ID]
"""

from pathlib import Path
from uuid import uuid4
import json
import os
import sys

from app.integrations.team_backend import TeamBackend

from agents.main import create_services
from agents.config import Settings
from agents.schemas.messages import InvestigationMessage


# -------------------------------------------------
# 1. Database paths
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

AGENT_DB = BASE_DIR / "agent_runtime.db"

ALERT_ID = sys.argv[1] if len(sys.argv) > 1 else "AL_3d8358dcb78db6b328ce_3"


# -------------------------------------------------
# 2. Connect to Member 1's PostgreSQL database
#    (DATABASE_URL / AML_SOURCE_DATABASE_URL)
# -------------------------------------------------

backend = TeamBackend(
    source_timezone=os.getenv("AML_SOURCE_TIMEZONE", "UTC"),
    window_hours=48,
    max_transactions=200,
    timeout_seconds=3,
)

print("\n[1] Reading Member 1 evidence...")

bundle = backend.get_alert_context(ALERT_ID)

print("Alert:", bundle.alert.alert_id)
print("Typology:", bundle.alert.typology)
print("Transactions:", len(bundle.transactions))


# -------------------------------------------------
# 3. Configure LangGraph agent services
# -------------------------------------------------

settings = Settings(
    _env_file=None,
    database_url="sqlite:///" + str(AGENT_DB),
    use_mock_backend=False,
    use_mock_llm=True,
    use_mock_rag=True,
    use_mock_service_bus=True,
    llm_provider="groq",
)

services = create_services(
    settings=settings,
    backend=backend,
)

# Fresh investigation ID for this test
investigation_id = "INV-M1-" + uuid4().hex[:12]

message = InvestigationMessage(
    alert_id=ALERT_ID,
    investigation_id=investigation_id,
)

print("\n[2] Starting LangGraph investigation...")
print("Investigation ID:", investigation_id)


# -------------------------------------------------
# 4. Execute the agent workflow
# -------------------------------------------------

try:
    result = services.runner.run(message)

    print("\n[3] Workflow execution finished")

except Exception as exc:
    print("\nWorkflow raised:", type(exc).__name__)

    # Retrieve any persisted failure information
    result = services.persistence.get(investigation_id)

finally:
    services.close()


# -------------------------------------------------
# 5. Inspect persisted investigation result
# -------------------------------------------------

if result is None:
    raise RuntimeError(
        "No persisted investigation result found"
    )

print("\n[4] Investigation result")

print(
    "Execution status:",
    result["execution_status"]
)

print("\nAgent execution trace:")

for run in result.get("agent_execution_trace", []):
    print(
        "-",
        run["agent_name"],
        ":",
        run["execution_status"]
    )

print("\nVerification:")

print(
    json.dumps(
        result.get("verification"),
        indent=2,
        default=str,
    )
)

print("\n[5] Report status")

if result.get("report") is not None:

    print("Report generated and persisted.")

    report_path = BASE_DIR / (
        investigation_id + "_report.json"
    )

    report_path.write_text(
        json.dumps(
            result["report"],
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print("Report saved:", report_path)

else:
    print("No report was persisted.")

print("\nPhase 4 execution complete.")
