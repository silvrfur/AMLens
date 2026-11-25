---
audience: developer
---

# Architecture decisions

These records describe decisions that are visible in the repository: in code, comments,
manifests or `DEPLOY.md`. Each one gives the context, the decision and its consequences, and
points to the evidence. The repository has no separate ADR log, so dates and authorship are not
recorded. Where the reason is not written down and has been reconstructed from the code,
the text says **Inferred**.

| # | Decision | Status |
|---|---|---|
| [ADR-001](#adr-001-same-origin-frontend-proxy-instead-of-cors) | Same-origin frontend proxy instead of CORS | Accepted |
| [ADR-002](#adr-002-shared-secret-between-proxy-and-backend) | Shared secret between proxy and backend; user identity from the edge | Accepted |
| [ADR-003](#adr-003-run-the-agents-in-process-inside-the-request) | Run the agents in-process, inside the HTTP request | Accepted, with known limits |
| [ADR-004](#adr-004-agent-runtime-store-in-postgresql-schema-agent_runtime) | Agent runtime store in PostgreSQL schema `agent_runtime` | Accepted |
| [ADR-005](#adr-005-aks-instead-of-azure-container-apps) | AKS instead of Azure Container Apps | Accepted (environment-driven) |
| [ADR-006](#adr-006-in-cluster-postgresql-statefulset-with-nightly-pg_dump) | In-cluster PostgreSQL StatefulSet with nightly `pg_dump` | Accepted (environment-driven) |
| [ADR-007](#adr-007-password-sign-in-through-oauth2-proxy) | Password sign-in through oauth2-proxy | Accepted, temporary |
| [ADR-008](#adr-008-azure-ai-search-with-verified-typology-pre-filter-and-040-cutoff) | Azure AI Search with verified-typology pre-filter and 0.40 cutoff | Accepted |
| [ADR-009](#adr-009-slim-rag-image-without-torch) | Slim RAG image without torch | Accepted |
| [ADR-010](#adr-010-human-in-the-loop-decisions-only) | Human-in-the-loop decisions only | Accepted |
| [ADR-011](#adr-011-constrained-llm-narrative-and-independent-verification) | Constrained LLM narrative and independent verification | Accepted |
| [ADR-012](#adr-012-keyed-tokenization-of-account-identifiers-at-ingestion) | Keyed tokenization of account identifiers at ingestion | Accepted |
| [ADR-013](#adr-013-alembic-owns-the-schema-the-app-refuses-to-start-otherwise) | Alembic owns the schema; the app refuses to start otherwise | Accepted |

---

## ADR-001: Same-origin frontend proxy instead of CORS

**Context.** The browser needs the backend and the RAG service. Exposing them publicly would
require CORS, a second sign-in boundary and public ingress for internal services. `NEXT_PUBLIC_*`
variables are frozen into the bundle at build time, so a browser-side base URL would force a
different image per environment.

**Decision.** The browser calls only the frontend origin. The Next.js route handler
`frontend/app/api/[service]/[...path]/route.ts` forwards `/api/backend/*` to
`AMLENS_BACKEND_URL` and `/api/rag/*` to `AMLENS_RAG_URL`, reading both at request time.

**Consequences.**

- Backend and RAG have no public ingress; NetworkPolicies allow the backend only from the
  frontend pod.
- One frontend image works everywhere (`frontend/Dockerfile`: "service URLs are runtime
  settings ... not build args").
- `AML_CORS_ORIGINS` and `RAG_CORS_ORIGINS` are empty in Compose and AKS; CORS remains only
  for local cross-origin development.
- Every API call has an extra hop through Node.js, and long calls (investigations) hold a
  connection in the proxy as well.

**Evidence.** Header comment of `route.ts`; `docker-compose.yml` (`AML_CORS_ORIGINS: ""`,
"same-origin via the frontend proxy"); `deploy/aks/base/network-policy.yaml`.

---

## ADR-002: Shared secret between proxy and backend

**Context.** Network isolation alone does not prove a request came through the authenticated
edge, and the backend must know which analyst made a decision.

**Decision.** The proxy adds `X-AMLens-Proxy-Key: <AMLENS_PROXY_KEY>` and
`X-AMLens-User: <signed-in user>`. The backend middleware `require_proxy` rejects requests
whose key does not match `AML_PROXY_KEY` (`hmac.compare_digest`) and trusts `X-AMLens-User`
only after the key matched. The user header is taken from `X-MS-CLIENT-PRINCIPAL-NAME`
(Container Apps Easy Auth) or `X-Auth-Request-Email` / `X-Auth-Request-User` (oauth2-proxy),
which the edge overwrites, never from the browser.

**Consequences.**

- `decide()` records `request.state.user` and ignores the `analyst_id` typed in the form.
- `/health` and `OPTIONS` are exempt so probes work.
- With `AML_PROXY_KEY` unset the backend is fully open; this is the local development mode
  and must never reach a deployment.
- The RAG service does not check the key. It relies on NetworkPolicy only.

**Evidence.** `backend/app/security.py`; `backend/tests/test_proxy_auth.py`;
`edge.yaml` annotation `auth-response-headers`.

---

## ADR-003: Run the agents in-process, inside the request

**Context.** The agents were developed as a separate package with their own FastAPI app,
an Azure Service Bus queue and a worker with retry and dead-lettering. The deployment
target allows a limited set of Azure services.

**Decision.** The backend imports the agents package (`agent_bridge.py`) and runs
`InvestigationRunner.run()` synchronously in `POST /investigations/{id}/run`. No queue is
deployed. `/health` reports `queue: "not_applicable"`.

**Consequences.**

- One image (`backend/Dockerfile` copies `agents/`) and no extra service to operate.
- The run is bound to the HTTP request: the ingress sets `proxy-read-timeout: "300"`, and
  the analyst waits about 30 seconds (`DEPLOY.md`).
- If the backend pod restarts mid-run, the agent lease (`lease_seconds`, default 900 s)
  and the case status `RUNNING` remain. **Inferred:** the run endpoint only accepts
  `PENDING_AGENT` or `FAILED`, so such a case needs manual repair.
- `DEPLOY.md` lists this as a remaining gap: "A Service Bus queue (the agents contain a
  worker) would make long or bulk runs survive restarts."
- The worker (`agents/worker/`), the agents' `create_app()` and `AzureServiceBus` are
  unused in production but kept tested (`agents/tests/test_worker.py`, `test_api.py`).

**Evidence.** `backend/app/api/investigations.py` (`run_investigation`),
`backend/app/api/health.py`, `deploy/aks/base/edge.yaml`, `DEPLOY.md`.

---

## ADR-004: Agent runtime store in PostgreSQL schema `agent_runtime`

**Context.** The agents persist reports, per-node runs, tool calls and an audit log. They
were built on SQLite. Container disks are wiped on restart, and more than one replica would
need a shared store. The agents' table names (`investigations`) collide with the backend's.

**Decision.** `create_store()` returns `PostgresService` for PostgreSQL URLs and
`SQLiteService` otherwise. `PostgresService` creates its tables in schema `agent_runtime`
(`CREATE SCHEMA IF NOT EXISTS`, under `pg_advisory_xact_lock(hashtext('agent_runtime_schema'))`)
and sets `search_path` per connection. Deployments point `AML_AGENT_DATABASE_URL` at the same
database as `DATABASE_URL`.

**Consequences.**

- Agent SQL is written once with `?` placeholders; the wrapper rewrites them to `%s`.
- Writers for one investigation are serialized with `pg_advisory_xact_lock(hashtext(id))`,
  the equivalent of SQLite's `BEGIN IMMEDIATE`.
- The `agent_runtime` tables are not managed by Alembic. Changing them means editing the
  `SCHEMA` string, and `CREATE TABLE IF NOT EXISTS` will not alter existing tables.
- Backups (`pg_dump` of the whole database) cover both stores.

**Evidence.** `agents/services/postgres_service.py`, `agents/main.py` (`create_store`),
`backend/app/services/agent_bridge.py`, `deploy/aks/base/apps.yaml`,
`agents/tests/test_postgres_store.py`.

---

## ADR-005: AKS instead of Azure Container Apps

**Context.** The intended design (`infra/main.bicep`) uses Container Apps with Easy Auth,
Key Vault, managed identities and PostgreSQL Flexible Server. The training sandbox
subscription "allows only AKS, VMs, ACR, Storage and Key Vault in one resource group in
`southindia` (no Container Apps, no managed PostgreSQL, no private DNS)".

**Decision.** The live deployment runs on AKS (`deploy/aks/`): two `Standard_B2s` nodes,
Azure CNI overlay with Cilium, the app-routing NGINX add-on, cert-manager with Let's Encrypt.
The Container Apps design stays in `infra/` for an unrestricted subscription.

**Consequences.**

- Two deployment definitions must be kept in step; the CI pipeline rolls out to AKS
  (`deploy/aks/rollout.sh`).
- Several platform features had to be rebuilt in-cluster: sign-in (oauth2-proxy), database
  (StatefulSet), backups (CronJob), network isolation (NetworkPolicy).
- Workload identity is not allowed in the sandbox, so Azure OpenAI and AI Search use keys
  stored as Kubernetes Secrets.
- Code comments still describe Container Apps Easy Auth (`security.py`, `route.ts`).

**Evidence.** `DEPLOY.md` (top note and AKS table), `deploy/aks/base/*.yaml`, `infra/`.

---

## ADR-006: In-cluster PostgreSQL StatefulSet with nightly `pg_dump`

**Context.** Managed PostgreSQL is not available in the sandbox (ADR-005).

**Decision.** PostgreSQL 16 (`postgres:16-alpine`) runs as a single-replica StatefulSet
with an 8 Gi `managed-csi` volume. The `postgres-backup` CronJob (`30 20 * * *`, 02:00 IST)
runs `pg_dump -Fc` and uploads it to Blob Storage with a create/write-only SAS; retention is
a 14-day storage lifecycle rule.

**Consequences.**

- No point-in-time restore; the recovery point is the last nightly dump.
- The cluster cannot read or delete existing backups (write-only SAS).
- Only pods labelled `amlens.io/db-client: "true"` can reach port 5432.
- A single replica means database downtime during node maintenance.

**Evidence.** `deploy/aks/base/postgres.yaml`, `backup.yaml`, `network-policy.yaml`,
`DEPLOY.md`.

---

## ADR-007: Password sign-in through oauth2-proxy

**Context.** Entra ID sign-in needs an app registration approved by a tenant admin. In the lab
tenant that consent was not available.

**Decision.** oauth2-proxy runs with the OIDC provider configured **and**
`--htpasswd-file`, `--display-htpasswd-form=true` and custom templates that hide the Entra
button. Analyst accounts are bcrypt entries in secret `amlens-htpasswd`, managed by
`deploy/aks/add-user.sh`. The sign-in Ingress is rate limited (`limit-rpm: "20"`).

**Consequences.**

- Password logins have no email, only a user name, so the proxy falls back to
  `X-Auth-Request-User` for `X-AMLens-User`.
- Account lifecycle (creation, reset, removal) is manual.
- Reverting is a manifest change: `edge.yaml` says to drop the three htpasswd/template flags
  once Entra is approved.

**Evidence.** `deploy/aks/base/edge.yaml` (comments on the oauth2-proxy args),
`deploy/aks/base/signin-templates.yaml`, `DEPLOY.md`, `route.ts` comment "Password logins have
no email, only a user name".

---

## ADR-008: Azure AI Search with verified-typology pre-filter and 0.40 cutoff

**Context.** Citations in an AML report must point to passages that really discuss the
alert's typology. Pure vector similarity returned passages on other AML topics. Only a small
set of passages has been manually verified per typology.

**Decision.** `TeamAzureSearchAdapter` runs one vector query on `content_vector` with
`filter="typology eq '<typology>'"` and `vector_filter_mode="preFilter"`, converts the
Azure score to cosine similarity (`2 - 1/score`) and drops results below `min_score = 0.40`.
Typology is set on a chunk only through `RAG/app/typology_annotations.py` (`VERIFIED_CHUNKS`).
The calibration comment records the evidence:

```python
# Calibrated 2026-11-24 on text-embedding-3-small, within the
# typology pre-filter (every candidate is a human-verified passage):
#   agent's descriptive queries .......... 0.46 - 0.66
#   other AML topics (e.g. onboarding) ... 0.27 - 0.37
#   unrelated text ....................... <= 0.12
# 0.40 keeps real agent queries and drops off-topic ones. The old
# 0.50 cutoff dropped every agent query, including structuring.
```

**Consequences.**

- Retrieval returns few results (one to three verified chunks per agent typology), and an
  empty result is normal and explained in `relevance_notes`.
- The evidence agent applies a second, stricter threshold for citing
  (`CITATION_MIN_RELEVANCE = 0.45`).
- The thresholds depend on the embedding model and corpus; both comments say to re-check
  them if either changes. `RAG/scripts/evaluate_azure_rag.py` hard-codes the same 0.40
  (`MIN_RELEVANCE`).
- Adding a typology requires a reviewed passage, an annotation and an index update
  ([RAG service](../modules/rag-service.md#how-to-add-a-typology)).

**Evidence.** `RAG/app/azure_search_adapter.py`, `agents/agents/evidence_agent.py`,
`RAG/scripts/add_verified_typology_chunks.py`, `RAG/scripts/update_azure_typologies.py`.

---

## ADR-009: Slim RAG image without torch

**Context.** The original RAG used FAISS with `sentence-transformers` (torch), which makes a
large image. The deployed backend is Azure AI Search, which needs only the Azure SDKs and the
OpenAI client.

**Decision.** `RAG/Dockerfile` installs `requirements-azure.txt` by default and sets
`RAG_BACKEND=azure`. `app/main.py` imports the FAISS pipeline lazily (`get_pipeline()`), and
`app/models.py` holds the response models without FAISS imports. A FAISS image is still
possible with `--build-arg RAG_REQUIREMENTS=requirements.txt`.

**Consequences.**

- `POST /retrieve` (FAISS pipeline) returns `503` in the deployed image.
- CI verifies the slim image contents by importing `app.main` in a venv with only
  `requirements-azure.txt`.
- The 4.5 MB FAISS index is still copied into the image even though it is unused with
  `RAG_BACKEND=azure`.

**Evidence.** `RAG/Dockerfile`, `RAG/requirements-azure.txt`, `RAG/app/main.py`,
`.github/workflows/ci-cd.yml`.

---

## ADR-010: Human-in-the-loop decisions only

**Context.** AML dispositions (closing an alert, escalating) have regulatory weight. An LLM
must not make or appear to make them.

**Decision.** Only `POST /investigations/{id}/decision` records `APPROVE`, `REJECT` or
`ESCALATE`, and it requires a human-entered rationale (10–5000 characters). The agents'
allowed tools are exactly `backend.read`, `rag.search` and `llm.generate`; the report schema
has no decision field; every report carries `HUMAN_DISCLAIMER`; the UI shows the banner
"AI-Generated Draft — Requires Investigator Review".

**Consequences.**

- `APPROVE` is rejected with 409 unless the run is `completed` and verification passed.
  `REJECT` and `ESCALATE` are allowed for `incomplete` reports.
- One decision per investigation (409 on a second one).
- The alert's status becomes `DECIDED` and never reopens.

**Evidence.** `backend/app/api/investigations.py` (`decide`),
`agents/services/security.py` (`ALLOWED_TOOLS`), `agents/schemas/report.py`,
`agents/tests/test_guardrails.py::test_no_decision_capability`,
`agents/tests/test_verifier.py::test_no_decision_action`.

---

## ADR-011: Constrained LLM narrative and independent verification

**Context.** LLM output can contain invented numbers, citations or accusations, and prompt
injection could arrive through transaction descriptions or retrieved text.

**Decision.** All facts, statistics, citations and gaps are computed deterministically
(`TransactionAgent`, `EvidenceAgent`, `InformationGapAgent`, `canonical_report`). The LLM
receives only `allowed_statements` and `allowed_next_steps` (`safe_llm_payload`) and returns a
`NarrativeDraft` choosing among them. `ReportVerifier` recomputes the canonical report from the
raw transactions and rejects any difference, unapproved sentence or accusatory wording.
One correction attempt is allowed; a report that still fails is persisted as `incomplete`.

**Consequences.**

- The narrative is formulaic by design.
- A failing LLM (`LLMUnavailable`) fails the run; a malformed LLM response leads to the
  correction path, not a failure.
- **Inferred:** the agent pipeline is near-deterministic, which makes verification exact
  equality rather than a similarity judgement.

**Evidence.** `agents/agents/report_agent.py`, `agents/verifier/report_verifier.py`,
`agents/prompts/agent_prompts.py`, `agents/graph.py`.

---

## ADR-012: Keyed tokenization of account identifiers at ingestion

**Context.** Uploaded files contain bank and account numbers. The workspace must not store
them, yet rules and history need a stable identifier per account.

**Decision.** `account_token(bank, account)` replaces each pair with
`ACC_` + the first 24 hex characters of an HMAC-SHA256 keyed with `TOKEN_SECRET` (≥ 32
characters), using a length-prefixed payload.

**Consequences.**

- `TOKEN_SECRET` cannot be rotated without breaking continuity with existing data
  (`DEPLOY.md`).
- Downstream components (agents, UI) only ever see tokens and further mask them.

**Evidence.** `backend/app/utils/tokenization.py`, `backend/tests/test_validation.py`.

---

## ADR-013: Alembic owns the schema; the app refuses to start otherwise

**Context.** The backend moved from SQLite (`aml.db`, ad-hoc migration scripts) to PostgreSQL.
Creating tables from the ORM at startup would hide drift between code and database.

**Decision.** Tables are created and changed only by Alembic. `assert_schema_current()` runs in
the FastAPI lifespan and raises if the database's revision differs from the code's heads.
On AKS a `migrate` Job runs before each rollout and the backend runs with
`RUN_MIGRATIONS=false`.

**Consequences.**

- A missed migration produces a crash loop with a clear message instead of runtime SQL errors.
- `DEPLOY.md`: migrations must stay backward compatible with the previous release, because
  they run before the new backend starts.
- `test_models_match_migrations` guards ORM/migration drift.

**Evidence.** `backend/app/database/schema_check.py`, `backend/app/main.py`,
`backend/alembic/versions/0001_initial_schema.py`, `deploy/aks/jobs/migrate.yaml`,
`backend/tests/test_migrations.py`.
