# AMLens / TraceIQ — Member 3

Standalone Python investigation assistant using real LangGraph, SQLite, Pydantic v2,
Pandas, the official Groq SDK, and Azure Service Bus. Offline defaults use deterministic
Groq/RAG fixtures and an in-memory queue. No agent can record an investigator decision.

## Quick start

Python 3.12 is the validated runtime. Run all commands from the extracted ZIP root
(the directory containing `agents/`), not from inside the package.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r agents/requirements-lock.txt
cp agents/.env.example .env
python -m pytest agents/tests -q
python -m agents.run_demo
uvicorn agents.main:app --host 127.0.0.1 --port 8000
```

`requirements.txt` contains supported version ranges; `requirements-lock.txt` records
the exact tested environment. No API key, Azure account or external database is needed.
The demo prints every report section, statistics, guidance metadata, evidence mappings,
gaps, verification history, execution order and persisted result. It demonstrates normal,
one-correction and incomplete cases. Its explicit mock settings override environment
credentials. Repeated demo invocations return the same persisted investigations, showing
idempotency. Delete **only** `agents/data/demo_runtime.db` to replay its three scenarios.

## Architecture

`main.create_services()` is the composition root; adapters can be injected. Agents never
instantiate provider clients. Deterministic agents do not need LLM calls; Agent 5 uses
the shared `StructuredLLM` interface. The workflow is a real compiled `StateGraph`:

```text
START -> transaction -> retrieval -> evidence -> information_gap -> report -> verify
verify pass -----------------------------------------------> persist -> END
verify fail -> correction -> reverify ---------------------> persist -> END
any execution failure ------------------------------------> persist failed -> END
```

There is exactly one correction route and no cycles. `retry_count` records that attempt.
A graph recursion limit is a secondary bound. ToolBudget caps backend reads, RAG searches,
and individual Groq requests (including provider retries) at eight per execution attempt.
Database persistence/auditing and broker settlement are internal operations outside that
external-tool budget. Retried queue deliveries start another bounded execution only if
no completed/incomplete result exists.

- **Transaction agent:** exact Decimal arithmetic and Pandas grouping. Totals/net flows
  are separate by currency. It computes rolling-hour velocity, round amounts, illustrative
  threshold clustering, distinct counterparties, fan-in/out and temporal deposit/withdrawal
  proximity. It does not infer unusualness against an unavailable historical baseline.
- **Retrieval agent:** deterministic targeted queries, typology filtering and at most two
  attempts. A relevance score below 0.65 causes query reformulation. Metadata is preserved;
  empty results remain empty. Weak passages cannot support an interpretation.
- **Evidence agent:** deterministic facts reference transaction IDs and metric keys;
  interpretations and concerns reference retrieved chunks and explicitly limited support.
  Intent is an unsupported assumption, never a conclusion about the customer.
- **Information gap agent:** seven case-information categories. Absent input means
  `not_provided`, not `confirmed_missing`. Explicit backend attestations distinguish
  available/verified, missing and not applicable.
- **Report agent:** Groq selects/orders approved evidence-grounded narrative sentences and
  follow-up actions. Python assembles the five typed sections and authoritative facts.
  Financial calculations and citation generation are never delegated to the model.

`InvestigationState` includes alert context, tokenised account ID, typed transactions,
analysis, retrieved guidance, claims, gaps/questions, report, verification, errors,
execution trace, status, correction count and lease ownership. Raw backend descriptions
and identifiers are excluded entirely from the LLM request. Account display identifiers
are SHA-256 pseudonyms; production should supply high-entropy tokens from Member 1.

## Verification and human control

The verifier independently recalculates statistics and reconstructs the expected facts,
references and information gaps. It rejects unknown IDs, changed source metadata, modified
figures, omitted sections/disclaimer/limitations and unapproved narrative or actions.
Reported sources are separate copies of the retrieval evidence to prevent shared-object
mutation. Narrative sentence allowlisting also rejects invented quantities written in
words, fabricated citations and accusatory statements. Verification errors and warnings
are retained even when correction succeeds.

The intentional tradeoff is constrained narrative expressiveness. This is deterministic
verification, not a claim that arbitrary prose can be fact-checked by a regex. Retrieved
source authenticity and legal applicability remain responsibilities of the trusted RAG
service and human investigator. Verbatim retrieved passages are data, never model commands.
No `record_decision` capability or final-decision API exists; investigation statuses do
not modify alert statuses. Recommended steps are review suggestions for humans only.

## Persistence and execution reliability

SQLite automatically initializes six tables: `alerts`, `transactions`, `investigations`,
`agent_runs`, `tool_calls`, `audit_log`. The first two form the synthetic source dataset;
BackendClient reads it, while Persistence manages investigation outputs. Report JSON is a
necessary immutable evidence snapshot, not another copy of the transaction-history table.
Execution events and safe exception classes are stored in audit records; prompts, API
keys, free-text errors and credentials are not logged. Tool-call rows record redacted
attempt metadata, not sensitive inputs or model outputs. Report and terminal audit event
are committed in one transaction. Enable logging with your deployment's logging config.

Atomic `BEGIN IMMEDIATE` claims prevent concurrent ownership. An investigation ID is bound
to one alert ID; reusing it for another alert is rejected. Completed/incomplete results
are idempotent. Failed attempts can retry. A 900-second lease allows recovery after a
worker crash; owner tokens fence stale writers. Long-running custom adapters must fit
within that lease or add a heartbeat before production use. API requests during active
ownership return 409. SQLite connections use foreign keys, WAL, timeouts, parameterized
queries and transaction rollback.

Execution states: `running`, `completed` (verification passed), `incomplete` (correction
still failed), `failed` (execution error). Incomplete reports remain available for review
with `verification.passed=false`; clients must never display them as verified.

## API and worker

```bash
curl -X POST http://127.0.0.1:8000/investigations/run \
  -H 'Content-Type: application/json' \
  -d '{"alert_id":"ALT-001","investigation_id":"INV-API-001"}'
curl http://127.0.0.1:8000/investigations/INV-API-001
curl http://127.0.0.1:8000/health
python -m agents.worker.service_bus_worker
```

`POST /investigations/queue` accepts the same JSON and returns 202 after successful send.
`POST /investigations/run` executes synchronously in FastAPI's threadpool. `GET` returns
report, verification, status, execution trace and audit history (404 before a queued
request is first claimed). Invalid requests are 422, ID conflicts/active claims 409,
execution or queue failures 503. OpenAPI documentation is at `/docs`.

The standalone mock worker enqueues and processes one sample. Mock queues are deliberately
process-local: an API's mock queue cannot be consumed by a separate worker process.
Tests/demo call `drain_mock` on the same Services instance. For actual background processing,
configure Azure for both API and worker. The Azure worker uses peek-lock receiving,
automatic lock renewal, bounded deliveries, abandon on retryable processing failure and
dead-letter on malformed/conflicting/exhausted messages. Acknowledgement happens only
once the result has persisted. Incomplete is a successful terminal persistence outcome;
it is acknowledged but remains visibly unverified. A failed acknowledgement may cause
redelivery, which reads the existing result without repeating inference.

## Configuration

Defaults are offline. To enable real Groq set `USE_MOCK_LLM=false`, `GROQ_API_KEY` and
`GROQ_MODEL` to an available model supporting JSON object chat completions. The SDK uses
JSON object mode plus local Pydantic validation, a 30-second timeout and up to three
attempts for connection/timeouts, rate limits and server failures. Authentication/client
errors are not retried. SDK internal retries are disabled to preserve the tool budget.
Groq availability and model IDs are not hard-coded; inspect your account's model catalog.

Set `USE_MOCK_RAG=false` with `RAG_SERVICE_URL` or inject Member 2's adapter.
Set `USE_MOCK_BACKEND=false` for existing SQLite data without synthetic seeding.
`DATABASE_URL` accepts `sqlite:///` paths; relative paths resolve against the working
directory. The included clean sample is `agents/data/synthetic_alerts.db`; `.env.example`
uses `./data/synthetic_alerts.db`, which is initialized/seeded automatically in mock mode.

Set `USE_MOCK_SERVICE_BUS=false`, `AZURE_SERVICE_BUS_CONNECTION_STRING`, and
`AZURE_SERVICE_BUS_QUEUE_NAME` for Azure. `MAX_DELIVERY_COUNT` defaults to 3; configure the
broker's delivery limit consistently. `LEASE_SECONDS` defaults to 900 (minimum 600).
Never commit `.env` files. All real network integrations need explicitly enabled settings.

## Tests and production scope

Tests exercise each agent, real LangGraph paths, real SQLite transactions and concurrent
claims, FAISS demo search, Groq SDK request/retry contracts, HTTP RAG contract, report
attacks, idempotency, broker retries/dead letters/ack failure and FastAPI integration.
They require no credentials. See `VALIDATION.md` for the actual recorded run.

This is Member 3's standalone module, not a production AML product. Member 1 retains
ownership of backend authentication, case management and final human decisions. Member 2
owns ingestion, embeddings, FAISS persistence and trusted source provenance. Deploy the
API behind Member 1's authentication/authorization and TLS before handling real case data.
Synthetic passages are labelled illustrative, not FATF or other regulatory quotations.
The USD 10,000 analysis parameter is illustrative, not a legal threshold. Temporal
proximity is not actual traced flow of funds. Current history analysis is intended for
small case windows; large histories require bounded/windowed retrieval and optimization.
Live Groq, Azure, and Member 2 services have SDK/contract tests but were not exercised with
real credentials. See `INTEGRATION_GUIDE.md` for exact replacement contracts.

## SDK references

Implementation checked against official documentation:
- [Groq structured outputs](https://console.groq.com/docs/structured-outputs)
- [LangGraph workflows](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/workflows-agents.mdx)
- [Azure Service Bus Python SDK](https://learn.microsoft.com/python/api/overview/azure/servicebus-readme)
