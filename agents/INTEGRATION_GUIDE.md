# Member 3 integration guide

All examples are Python imports from the extracted ZIP root. Keep adapters behind the
composition root (`agents.main.create_services`). Do not add provider SDK calls to agents.

## Member 1 — backend / SQLite

Implement the `BackendClient` protocol:

```python
from agents.schemas.investigation import AlertBundle

class TeamBackend:
    def get_alert_context(self, alert_id: str) -> AlertBundle:
        # Read your SQLite schema or call your authorized backend API here.
        # Return validated data; no decision-writing operation is needed.
        ...
```

For custom backend adapters call `agents.services.audit_service.consume('backend.read')`
**before each external read attempt**, including retries. The built-in SQLite adapter
already does this. Use timeouts and fit within the workflow's total lease. Return only
the relevant account's history and include the transaction that triggered the alert.
Missing alerts should raise KeyError. No data means a processing failure, not a guessed
alert. Report retrieval is `services.persistence.get(investigation_id)`.

Expected alert:

```json
{
  "alert_id": "ALT-001", "transaction_id": "TX-001",
  "label": "Synthetic review alert", "typology": "structuring",
  "status": "open", "created_at": "2026-01-10T11:00:00Z",
  "information_status": {"kyc": "available_verified", "source_of_funds": "confirmed_missing"}
}
```

Supported typologies: `structuring`, `rapid_movement`, `fan_in_out`, `unusual_activity`.
Map upstream categories explicitly or extend the validated contract and tests together.
Information status is optional: missing keys mean `not_provided`. Valid status values:
`confirmed_missing`, `not_provided`, `not_applicable`, `available_verified`.
Fields: `kyc`, `source_of_funds`, `transaction_purpose`,
`sender_beneficiary_relationship`, `counterparty_information`, `economic_rationale`,
`supporting_documents`. Supply `available_verified` only from actual case verification.

Expected transaction:

```json
{
  "transaction_id": "TX-001", "account_token": "opaque-account-token",
  "counterparty_token": "opaque-counterparty-token", "amount": "9800.00",
  "currency": "USD", "timestamp": "2026-01-10T09:00:00+00:00",
  "transaction_type": "deposit", "description": "Untrusted source description"
}
```

Return `AlertBundle(alert=..., transactions=[...])`. Amounts must be positive decimal
strings with at most two decimal places; direction is `deposit` or `withdrawal` relative
to this account. Timezones are required. Do not pass floating-point money or raw PII.
Transactions must have unique IDs, all belong to the anchor account and represent a
bounded case-history window. Extra properties are rejected to make schema drift visible.
Descriptions and alert labels are never forwarded to the LLM. For currencies needing
other minor-unit precision, revise the schema and deterministic arithmetic tests first.

Composition:

```python
from agents.main import create_services, create_app
from agents.config import Settings
services = create_services(Settings(use_mock_backend=False), backend=TeamBackend())
app = create_app(services=services)
```

Alternatively point DATABASE_URL at a compatible shared SQLite database and disable mock
backend seeding. Do not assume the standalone schema is the final team schema. Only
`SQLiteBackendClient` needs adapting for changed source tables. Persistence tables can
remain in a separate local DB by injecting TeamBackend with its own storage connection.

Standalone schema is defined in `services/sqlite_service.py`. `alerts.transaction_id`
references `transactions.transaction_id`; transactions store tokenized accounts and decimal
text amounts. `investigations` has the requested report/verification/status/timestamps plus
`lease_owner` and `lease_until` for idempotency. Runs reference investigations; tool calls
reference runs; audit events reference investigations. Alerts and transactions are never
updated by the workflow. Only the explicit mock seeder inserts synthetic source rows.

### Azure publishing

Backend publishes UTF-8 JSON to the configured queue:

```json
{"alert_id":"ALT-001","investigation_id":"INV-001"}
```

Use a unique investigation ID per intentional new investigation; retries reuse the same ID.
Set the broker message ID to the investigation ID when practical. Completed or incomplete
IDs are immutable/idempotent; use a new ID to investigate changed source data. Reusing an
ID for another alert dead-letters with `InvestigationIdConflict`. There is no human decision
field or decision-writing endpoint. Configure both producer and consumer with the same
Azure queue. Consume with `python -m agents.worker.service_bus_worker` after disabling
mock Service Bus. The client handles message locking/renewal; operations must provide
access controls, secrets, networking, broker limits and DLQ monitoring/replay procedures.
If replaying exhausted failures, first correct the cause, then resubmit the same ID if its
persisted execution status is failed. An incomplete result requires human review or a new ID.

## Member 2 — FAISS RAG

Implement this synchronous interface (or wrap your async service in an HTTP endpoint):

```python
from agents.schemas.agent_outputs import RetrievalResult
class TeamFAISSAdapter:
    def search_aml_guidance(self, query: str, typology: str, top_k: int = 5) -> RetrievalResult:
        ...
```

Inject via `create_services(settings, rag=TeamFAISSAdapter())`. Or expose `POST /search`
and set `USE_MOCK_RAG=false`, `RAG_SERVICE_URL=https://your-service`. The built-in HTTP
adapter sends `{"query":"...","typology":"structuring","top_k":5}` with a timeout.
It validates the complete response and preserves metadata. It does not run its own retries:
Agent 2 controls the two-search budget. Custom RAG adapters should perform one search per
call; Agent 2 charges that call to the tool budget. Hidden adapter retries must explicitly
consume another `rag.search` budget slot or be disabled.

Response:

```json
{
  "retrieved_guidelines": [{
    "chunk_id": "CHUNK-001",
    "text": "Exact passage from your approved guidance corpus",
    "source": "Actual source title", "section": "Section 2", "page": 5,
    "typology": "structuring", "relevance_score": 0.89
  }],
  "source_references": ["CHUNK-001"],
  "relevance_notes": ["Optional retrieval limitation"]
}
```

Use stable unique chunk IDs, verbatim passages, real source names/sections/pages (page may
be null), matching typologies and scores normalized to [-1, 1] with **higher = more relevant**.
Convert FAISS distance metrics to that contract in your adapter. A relevance cutoff of 0.65
is an illustrative application parameter needing calibration to your embedding model.
Preserve source authenticity and approved document provenance in your service. The module
validates report citations against returned chunks; it cannot prove that a service supplied
authentic regulatory text. Do not generate passages if the search has no hits: return empty
lists. Low relevance triggers one reformulated query. Schema/network failure is an execution
failure, not permission to invent guidance. `source_references` are service metadata;
claim-level citations use `supporting_chunk_ids`. Report references retain full chunk objects.
Display citations as `source — section — page (chunk_id)`; page is omitted when null.
The report verifier rejects any altered citation metadata or unknown referenced chunk.

`mocks/local_faiss.py` is an optional working FAISS IndexFlatIP demo using small lexical
vectors and the illustrative guidance JSON. It is not the production embedding/indexing
pipeline. Default MockRAGClient uses deterministic fixtures so tests are fully offline.

## Groq and report contract

`StructuredLLM.generate_structured_response(system_prompt, user_input, response_schema)`
returns a validated Pydantic object. `GroqLLM` owns model-specific JSON mode, timeout and
transient retries. `MockGroqClient` is deterministic and supports correction fault injection.
If replacing this abstraction, charge **each actual request** to `llm.generate` and keep
prompt contents/exception text out of logs. Model names are configured, never guessed.

The structured Groq response is `NarrativeDraft(statements, recommended_next_steps)`.
The report agent then constructs and validates `InvestigationReport`, with five mandatory
sections and a human-review disclaimer. This deliberately restricts the model to selection
and ordering of validated statements, while deterministic code controls numbers and evidence.
Expanding to free prose requires a separately designed semantic verification layer and
additional adversarial tests; do not silently disable the current allowlist.

## Runtime and UI handoff

Run or queue endpoint bodies use `InvestigationMessage`. Fetching an investigation returns
its persisted report, verification and audit trace. A UI should show warnings, source IDs,
limitations, and unverified/incomplete status prominently. Human decision controls belong
to Member 1's separate authorized backend. The agent module offers no such capability.
API authentication, multi-user authorization, retention policies and deployment are external
integration responsibilities; the local server binds to loopback in the documented command.
Mock queues cannot communicate across processes. Live Azure should be used for the actual
split API/worker deployment. SQLite WAL is suited to this single-host prototype, not a
shared network filesystem or distributed database substitute.
