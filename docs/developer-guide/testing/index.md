---
audience: developer
---

# Testing

AMLens has two automated pytest suites (agents and backend), a type-check and production build
for the frontend, and an import check for the RAG service. CI runs all of them on every pull
request and every push to `main`; a failure blocks the deployment job.

## At a glance

| Component | Framework | Location | Tests (measured) | External services |
|---|---|---|---|---|
| Agents | pytest 8+ | `agents/tests/` (config `agents/pytest.ini`) | **98** collected: 95 pass offline, 3 PostgreSQL-store tests skip without `AML_AGENT_TEST_DATABASE_URL` | None. Sockets to anything but `127.0.0.1` fail the test. |
| Backend | pytest 8+, FastAPI `TestClient`, Alembic | `backend/tests/` (config `backend/pytest.ini`) | **22** collected | A real, throwaway PostgreSQL database (`TEST_DATABASE_URL`). LLM and RAG are always mocked. |
| RAG | none (import check in CI) | `RAG/app/test_*.py` are **manual scripts**, not pytest tests | 0 | - |
| Frontend | TypeScript compiler, `next build` | - | 0 unit tests | - |

!!! info "How these numbers were measured"
    With the repository root on `PYTHONPATH`:
    `python -m pytest agents/tests --collect-only -q` → 98 tests;
    `cd backend; python -m pytest --collect-only -q` → 22 tests. A full agents run
    (`python -m pytest agents/tests -q`) gave **95 passed, 3 skipped** in about 84 s on
    Windows with Python 3.14. The backend suite was collected but **not run** for this guide
    (it needs the Docker database). `pnpm exec tsc --noEmit` in `frontend/` exited cleanly.
    `backend/README.md` ("17 passed") and `agents/VALIDATION.md` ("74 passed") are older.

## Running the tests

All commands start at the repository root and assume the shared `.venv` from
[Installation](../getting-started/installation.md).

=== "PowerShell"

    ```powershell
    $env:PYTHONPATH = (Get-Location).Path

    # Agents (offline)
    .venv\Scripts\python -m pytest agents\tests -q

    # Backend (start the database first: cd backend; docker compose up -d)
    cd backend; ..\.venv\Scripts\python -m pytest -q; cd ..

    # Frontend type-check and production build
    cd frontend; npx pnpm exec tsc --noEmit; cd ..
    cd frontend; $env:NEXT_PUBLIC_USE_MOCKS = "false"; npx pnpm build; cd ..
    ```

=== "Bash"

    ```bash
    export PYTHONPATH="$(pwd)"

    # Agents (offline)
    .venv/bin/python -m pytest agents/tests -q

    # Backend (start the database first: (cd backend && docker compose up -d))
    (cd backend && ../.venv/bin/python -m pytest -q)

    # Frontend type-check and production build
    (cd frontend && npx pnpm exec tsc --noEmit)
    (cd frontend && NEXT_PUBLIC_USE_MOCKS=false npx pnpm build)
    ```

Useful pytest options:

```bash
python -m pytest agents/tests/test_verifier.py -q            # one file
python -m pytest agents/tests -q -k "correction"             # by name
python -m pytest agents/tests -q -x --lf                     # stop at first failure, rerun last failures
```

### Running the PostgreSQL tests locally

The Docker database from `backend/docker-compose.yml` already has an `amlens_test` database.

=== "PowerShell"

    ```powershell
    $env:PYTHONPATH = (Get-Location).Path
    $env:AML_AGENT_TEST_DATABASE_URL = "postgresql://amlens:amlens_dev@127.0.0.1:5433/amlens_test"
    .venv\Scripts\python -m pytest agents\tests\test_postgres_store.py -q
    ```

=== "Bash"

    ```bash
    export PYTHONPATH="$(pwd)"
    export AML_AGENT_TEST_DATABASE_URL=postgresql://amlens:amlens_dev@127.0.0.1:5433/amlens_test
    .venv/bin/python -m pytest agents/tests/test_postgres_store.py -q
    ```

The backend suite reads `TEST_DATABASE_URL` from `backend/.env` (the template already sets
it to `…/amlens_test`).

!!! danger "Test databases are wiped"
    Both suites destroy data: the backend fixtures run `alembic downgrade base` and
    `TRUNCATE` the tables; the agent PostgreSQL tests `DROP SCHEMA agent_runtime CASCADE`.
    Both refuse to run unless the **database name contains `test`**. Never point these
    variables at a database you care about.

## How CI runs the tests

The `test` job in `.github/workflows/ci-cd.yml` runs on `ubuntu-latest` for every pull
request, every push to `main`, and manual runs.

```mermaid
flowchart TD
    trigger["pull_request / push to main / workflow_dispatch"] --> svc["Service container: postgres:16<br/>db amlens_test on port 5433"]
    svc --> py["setup-python 3.12<br/>pip install backend + agents requirements"]
    py --> agents["python -m pytest agents/tests -q<br/>(SQLite + PostgreSQL stores)"]
    agents --> backend["cd backend; python -m pytest -q<br/>(mock LLM/RAG, real PostgreSQL)"]
    backend --> rag["RAG import check<br/>requirements-azure.txt, no torch"]
    rag --> fe["pnpm (from packageManager) + Node 20<br/>pnpm install --frozen-lockfile<br/>tsc --noEmit, pnpm build"]
    fe --> deploy{"main branch push<br/>or manual run?"}
    deploy -->|yes| roll["deploy job: deploy/aks/rollout.sh"]
    deploy -->|no| done["done"]
```

| Setting | Value in CI |
|---|---|
| PostgreSQL | `postgres:16` service, user `amlens` / `amlens_dev`, database `amlens_test`, published on `5433`, health-checked with `pg_isready` |
| `PYTHONPATH` | the workspace root (so `import agents` works) |
| `TEST_DATABASE_URL` | `postgresql+psycopg://amlens:amlens_dev@127.0.0.1:5433/amlens_test` |
| `AML_AGENT_TEST_DATABASE_URL` | `postgresql://amlens:amlens_dev@127.0.0.1:5433/amlens_test` |
| RAG check | Fresh venv with `RAG/requirements-azure.txt`, then `from app.main import app` with dummy `RAG_BACKEND=azure` settings. Proves the Azure image imports without the FAISS/torch stack; it does **not** test retrieval. |
| Frontend | `NEXT_PUBLIC_USE_MOCKS=false`, `pnpm install --frozen-lockfile`, `pnpm exec tsc --noEmit`, `pnpm build` |

Because CI sets `AML_AGENT_TEST_DATABASE_URL`, the three PostgreSQL-store tests that skip on
your machine **run in CI**. Run them locally (above) when you touch
`agents/services/postgres_service.py`.

## Agents suite

### Layout

| File | Collected | Covers |
|---|---:|---|
| `conftest.py` | - | Shared fixtures (below) |
| `test_transaction_agent.py` | 5 | Exact Decimal statistics, currency separation, empty input, duplicate/mixed-account rejection, no baseline claims |
| `test_retrieval_agent.py` | 6 | Metadata and typology filter, reformulation, typology described in words, weak results kept, HTTP RAG contract, toy local FAISS |
| `test_evidence_agent.py` | 3 | Claims trace to transactions/metrics, citation threshold, no interpretation without guidance |
| `test_information_gap_agent.py` | 2 | Absent ≠ confirmed missing; explicit statuses |
| `test_report_agent.py` | 2 | Complete report via the shared LLM interface; prompt excludes accounts and descriptions |
| `test_verifier.py` | 17 | Accepts grounded reports; rejects tampering (parametrised); no decision actions; grounding cannot be mutated |
| `test_graph.py` | 7 | Real LangGraph sequence, single correction, failure persisted, tool-budget limits, invalid structured output |
| `test_guardrails.py` | 4 | Masking, prompt-injection text not forwarded, no decision capability, redacted tool logs |
| `test_azure_openai_llm.py` | 18 | Azure OpenAI SDK arguments, JSON validation, retries, timeouts, non-retried 4xx, Entra ID token provider, v1 endpoint, provider factory |
| `test_groq_llm.py` | 8 | The same contract for Groq |
| `test_config.py` | 5 | Offline defaults, secrets not printed, provider validation |
| `test_sqlite.py` | 5 | Parameterised reads, rollback, conflicts, concurrent claims, lease fencing |
| `test_postgres_store.py` | 3 | Full run persisted to PostgreSQL, idempotency/conflicts, live lease (skipped without `AML_AGENT_TEST_DATABASE_URL`) |
| `test_api.py` | 3 | Standalone FastAPI app: run, get, health, queue, validation, missing alert |
| `test_worker.py` | 8 | Service Bus handler: persist-then-ack, retries, dead-lettering, ack failure, SDK contract |
| `test_integration.py` | 2 | Offline end to end through the worker; no-guidance baseline |

### Fixtures (`agents/tests/conftest.py`)

| Fixture | Scope | What it provides |
|---|---|---|
| `services` | function | `create_services(Settings(_env_file=None, database_url=sqlite:///<tmp>/test.db, use_mock_llm=True, use_mock_rag=True, use_mock_backend=True, use_mock_service_bus=True))`: a full service graph on a fresh SQLite file in `tmp_path`, closed after the test. `_env_file=None` ensures a developer's `.env` cannot switch a test to live services. |
| `message` | function | `InvestigationMessage(alert_id='ALT-001', investigation_id='INV-TEST')` |
| `state` | function | A pipeline state after running the transaction, retrieval, evidence and information-gap agents on `ALT-001`, ready for report and verifier tests. |
| `no_external_network` | function, **autouse** | Patches `socket.create_connection` and `socket.socket.connect` so any connection that is not to `127.0.0.1` raises `AssertionError('Offline tests must not connect to external services')`. Loopback stays allowed for asyncio's self-pipe on Windows. |

### Mocks (`agents/mocks/`)

| Module | Class / data | Behaviour |
|---|---|---|
| `mock_groq.py` | `MockGroqClient(fail_first=False, always_fail=False)` | Deterministic LLM. Returns the allowed statements and next steps unchanged; records calls. `fail_first` injects one invented figure (`999999 USD`) to exercise the correction route; `always_fail` forces an incomplete report. Used whenever `USE_MOCK_LLM=true`, whatever the provider. |
| `mock_rag.py` | `MockRAGClient` | Returns illustrative guidance chunks for the requested typology from `sample_data.GUIDANCE`; records queries. |
| `mock_backend.py` | `MockBackendClient(db)` | A real `SQLiteBackendClient` over a store seeded idempotently with synthetic data. |
| `sample_data.py` | `GUIDANCE`, `seed(db)` | Three illustrative guidance chunks (structuring, rapid movement, fan-in/out) and six transactions / two alerts (`ALT-001` structuring, `ALT-002` unusual activity). Clearly labelled as not regulatory guidance. |
| `local_faiss.py` | `LocalFAISSDemoClient` | Toy lexical FAISS index over the sample guidance, for the FAISS test only. |

## Backend suite

### Layout

| File | Collected | Needs | Covers |
|---|---:|---|---|
| `test_api.py` | 6 | PostgreSQL + `agents` | Upload → alerts → case → mock agent run → decision → audit; alert status lifecycle; duplicate upload rejected; tokenised history with exact amounts; pending investigation shape; health per service |
| `test_migrations.py` | 3 | PostgreSQL | Upgrade/downgrade round trip; ORM models match migrations (Alembic autogenerate diff is empty); app refuses an un-migrated database |
| `test_team_backend.py` | 4 | PostgreSQL + `agents` | Agent adapter builds `AlertBundle`s, history limit, read-only transactions, missing `created_at` rejected |
| `test_proxy_auth.py` | 4 | - | `AML_PROXY_KEY` middleware: open without a key, rejects wrong/missing key, trusts `X-AMLens-User` only with the key, `/health` stays open |
| `test_transaction_analysis.py` | 3 | - | Detection rules: self-transfers, high value, repeated pairs within the window |
| `test_validation.py` | 2 | - | CSV validation and bad amounts; account tokens are stable and bank-scoped |

`backend/pytest.ini` sets `testpaths = tests`, so `backend/test_real_integration.py` and
`backend/phase4_run.py` (manual tools) are never collected.

### Fixtures (`backend/tests/conftest.py`)

At import, `conftest.py` puts `backend/` and the repository root on `sys.path`, loads
`backend/.env`, sets default `TOKEN_SECRET` and `AML_SOURCE_TIMEZONE`, **forces
`USE_MOCK_LLM=true` and `USE_MOCK_RAG=true`**, and, when `TEST_DATABASE_URL` is set, points
`DATABASE_URL` at it and removes `AML_SOURCE_DATABASE_URL`.

| Fixture | Scope | What it provides |
|---|---|---|
| `pg_url` | session | The normalised `TEST_DATABASE_URL`. **Skips** the test if unset; **exits** pytest if the database name lacks `test`. |
| `alembic_cfg` | session | Alembic config pointed at `pg_url`. |
| `migrated_db` | session | Runs `alembic downgrade base` then `upgrade head` once per session. |
| `clean_db` | function | Re-applies `upgrade head`, truncates all six tables, and sets `AML_AGENT_DATABASE_PATH` to a SQLite file in `tmp_path`. Yields the SQLAlchemy engine. |

`test_api.py` and `test_team_backend.py` call `pytest.importorskip('agents')`: without
`PYTHONPATH` they are **skipped**, not failed. A run with many skips usually means the
database is down or `PYTHONPATH` is missing.

## RAG checks

`RAG/app/test_azure_adapter.py`, `test_prompt.py`, `test_rag_pipeline.py` and
`test_retriever.py` contain no `test_` functions; they are interactive scripts (some call
`input()`), and `RAG/scripts/test_azure_connections.py` / `test_azure_retrieval.py` call
live Azure services. Run them by hand from `RAG/` with the RAG venv, for example
`.venv\Scripts\python -m app.test_retriever`. The RAG service's HTTP contract is tested
from the agents side (`test_retrieval_agent.py::test_http_contract`).

`RAG/scripts/evaluate_azure_rag.py` evaluates retrieval quality against a running service
(`RAG_EVAL_URL`). It is an evaluation tool, not part of CI.

## Adding a test

### Agents

1. Add `agents/tests/test_<area>.py`. Use the `services`, `message` or `state` fixtures
   rather than building settings yourself; if you must, pass `_env_file=None` and explicit
   mock flags.
2. Inject fakes through `create_services(settings, backend=…, rag=…, llm=…, bus=…)` or
   `unittest.mock`. Never call a real provider: the autouse network guard will fail the test.
3. For provider adapters, follow `test_azure_openai_llm.py`: mock the SDK client and assert
   on the arguments, retries and errors.

```python
def test_observed_facts_cite_transactions(state):
    # `state` has already been through the transaction, retrieval, evidence and gap agents.
    facts = [f for f in state['evidence_findings'] if f.claim_type == 'observed_fact']
    assert facts
    assert all(f.supporting_transaction_ids for f in facts)
```

### Backend

1. Add `backend/tests/test_<area>.py`.
2. For anything touching the database, depend on `clean_db` (it skips cleanly without a
   database). For HTTP tests, build a `TestClient(app)` inside a fixture that depends on
   `clean_db`, as `test_api.py` does.
3. If the test needs the agents package, start the module with
   `pytest.importorskip('agents', reason=…)`.
4. Pure functions (validation, rules, tokenisation) need no fixture.

```python
import pytest

pytest.importorskip('agents', reason='agents package not on PYTHONPATH')


@pytest.fixture
def client(clean_db):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_alerts_empty_on_fresh_database(client):
    response = client.get('/alerts')
    assert response.status_code == 200
    assert response.json()['total'] == 0
```

### Schema changes

A new Alembic migration is covered automatically: `test_models_match_migrations` fails if
the ORM models in `app/database/tables.py` and the migrations disagree, and
`test_upgrade_downgrade_roundtrip` fails if `downgrade()` does not cleanly reverse
`upgrade()`. See [Migrations](../database/migrations.md).

## Testing gaps

These are known, verified gaps. Treat them as risk when you change the related code.

| Gap | Impact | Recommendation |
|---|---|---|
| **No frontend unit, component or end-to-end tests.** `frontend/package.json` has no `test` script and no Jest, Vitest or Playwright dependency. | UI regressions, mock/live mapping errors in `lib/api/client.ts` and proxy bugs are caught only by the type-check, the build, or by hand. | Click through every page in both mock and live mode before merging UI changes. Consider Vitest for `lib/api/client.ts` and the proxy route, and Playwright for the first-case flow. |
| **No linting or formatting checks** in any component (no ESLint, Ruff, Black or Prettier configuration). | Style drifts; some bug classes (unused imports, missing `await`) go unnoticed. | Follow the surrounding style; run your editor's linter. |
| **RAG service has no automated tests.** CI only checks that the Azure image imports. | Changes to `/search`, typology filtering or the score threshold (`min_score = 0.40`) are unverified. | Test by hand against Azure and with `evaluate_azure_rag.py`; consider pytest tests with a mocked `SearchClient`. |
| **Live Azure OpenAI, Azure AI Search and Service Bus are never called in tests.** They are covered only by SDK-contract tests with mocks. | Credential, deployment-name, quota and content-filter problems appear only at runtime. | Smoke-test a real investigation after configuration changes (*Settings → Service health*, then run one alert). |
| **No tests for the deployment scripts and manifests** (`deploy/aks/`, `infra/`). | A broken rollout is detected only by the deploy job's smoke test. | Review manifest changes carefully; see [CI/CD pipeline](../deployment/ci-cd.md). |
| **No load or performance tests.** Upload validation is in-memory (limit 100,000 rows / 20 MB) and investigations run inside the HTTP request. | Large uploads or concurrent runs are untested. | Keep within the documented limits. |
| **Backend coverage is thin outside the main flow** (22 tests). | Edge cases in `api/investigations.py` and `services/ingestion.py` may be untested. | Add a test with every bug fix. |
