---
audience: developer
---

# Configuration

Every AMLens service is configured through **environment variables**. This page lists every
variable the code reads, per service, built from the code that reads them (`os.getenv` /
`os.environ` calls, the `agents.config.Settings` fields, and `process.env` in the frontend),
then explains the handful that cause most problems.

!!! danger "Secrets are placeholders here"
    Values such as `<at least 32 random characters>` are placeholders. Real keys, passwords
    and the team's `TOKEN_SECRET` are shared privately and live only in git-ignored `.env`
    files, Kubernetes Secrets or Key Vault. Never commit them, and never put them in a
    `NEXT_PUBLIC_*` variable (those are compiled into the browser bundle).

## How settings are loaded

| Service | Where values come from | Precedence |
|---|---|---|
| Backend (`backend/`) | Process environment, plus `backend/.env` loaded by `python-dotenv` in `app/database/connection.py` | **Real environment variables win** over `.env` |
| Agents inside the backend | The same process environment; `app/services/agent_bridge.py` builds `agents.config.Settings(_env_file=None, …)` and pins the store, backend adapter and queue | Bridge overrides > environment > `Settings` defaults |
| Agents standalone (`agents.main:app`, demo, worker) | `agents.config.Settings` (pydantic-settings): environment plus `.env` in the **current directory** | Environment > `.env` > defaults |
| RAG (`RAG/`) | Process environment, plus `RAG/.env` loaded with `override=True` | **`RAG/.env` wins** over the environment (the Docker image does not contain `.env`, so there the environment applies) |
| Frontend server (proxy) | `process.env` at **request time**: `AMLENS_*` | Runtime; change and restart |
| Frontend browser bundle | `NEXT_PUBLIC_*`, inlined at **build time** (`next build`) or when `next dev` starts | Rebuild/restart to change |

Templates: `backend/.env.example`, `agents/.env.example`, `RAG/.env.example`. The frontend
has no template; create `frontend/.env.local` by hand when you need live services.

Boolean flags read by `agents.config.Settings` accept pydantic's forms (`true`/`false`,
`1`/`0`, `yes`/`no`, `on`/`off`). The backend health check reads `USE_MOCK_RAG` itself and
treats anything other than `false`, `0` or `no` as true.

## Backend (`backend/`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | **Yes** | none (the app raises `DATABASE_URL is not set`) | Main AML database. Must be PostgreSQL: `postgres://`, `postgresql://` and `postgresql+psycopg://` are accepted and normalised to psycopg 3; anything else, including SQLite, is rejected. Template value: `postgresql+psycopg://amlens:amlens_dev@127.0.0.1:5433/amlens`. Also used by Alembic. |
| `DB_POOL_SIZE` | No | `5` | SQLAlchemy connection pool size. |
| `DB_MAX_OVERFLOW` | No | `10` | Extra connections above the pool size. |
| `AML_SOURCE_DATABASE_URL` | No | falls back to `DATABASE_URL` | Separate login the agent adapter (`TeamBackend`) uses to read alerts and transactions, e.g. a SELECT-only role from `scripts/create_readonly_role.sql`. Reads are `READ ONLY` transactions either way. |
| `TOKEN_SECRET` | **Yes** (for uploads) | none | HMAC-SHA256 key for account tokenisation. At least 32 characters; must be the **team's shared value**. See [below](#token_secret). |
| `AML_SOURCE_TIMEZONE` | **Yes** (for agent runs) | none in code; `UTC` in the template | Timezone of the source transaction timestamps, which carry none. Runs fail with `Set AML_SOURCE_TIMEZONE explicitly…` if unset. |
| `AML_AGENT_DATABASE_URL` | No locally; **yes in deployments** | unset → SQLite file | Store agent runs in PostgreSQL (schema `agent_runtime`). May be the same database as `DATABASE_URL`. Must be a PostgreSQL URL. See [below](#aml_agent_database_url). |
| `AML_AGENT_DATABASE_PATH` | No | `./agent_runtime.db` | SQLite file for agent runs when `AML_AGENT_DATABASE_URL` is unset. Relative to the working directory; must end in `.db`, `.sqlite` or `.sqlite3`. |
| `AML_CORS_ORIGINS` | No | unset → no CORS middleware | Comma-separated browser origins allowed to call the API directly. Not needed with the frontend proxy. Never `*`. |
| `AML_PROXY_KEY` | No locally; **yes in deployments** | unset → every request accepted | Shared secret the frontend proxy must send in `X-AMLens-Proxy-Key`. See [below](#aml_proxy_key-and-amlens_proxy_key). |
| `RUN_MIGRATIONS` | No (Docker image only) | `true` in `backend/Dockerfile` | When `true`, the container runs `alembic upgrade head` before Uvicorn. See [below](#run_migrations). |
| `PYTHONPATH` | **Yes** outside Docker | `/app` in the image | Must include the repository root so `import agents` works. |
| `TEST_DATABASE_URL` | Tests only | none → database tests skipped | Throwaway PostgreSQL database for `backend/tests`. The database name **must contain `test`**; it is wiped. Template: `…/amlens_test`. |

The backend also passes these agent settings through (read by `agents.config.Settings`
inside the backend process):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `USE_MOCK_LLM` | No | `true` | `true` uses the deterministic offline LLM (`MockGroqClient`). Set `false` for Azure OpenAI or Groq. |
| `LLM_PROVIDER` | No | `azure_openai` | `azure_openai` or `groq`. |
| `AZURE_OPENAI_ENDPOINT` | When live and `azure_openai` | empty | e.g. `https://<resource>.openai.azure.com/`, or an endpoint ending in `/openai/v1/` for the v1 API. |
| `AZURE_OPENAI_DEPLOYMENT` | When live and `azure_openai` | empty | The chat **deployment** name (not the model name). Must support JSON mode. |
| `AZURE_OPENAI_API_KEY` | No | empty → Entra ID | Key auth. Empty uses `DefaultAzureCredential` (`az login` locally, managed identity in Azure; role *Cognitive Services OpenAI User*). Secret. |
| `AZURE_OPENAI_API_VERSION` | No | `2024-10-21` | API version; `v1` (or a `/openai/v1/` endpoint) sends none. |
| `GROQ_API_KEY` | When `LLM_PROVIDER=groq` | empty | Groq key. Secret. |
| `GROQ_MODEL` | When `LLM_PROVIDER=groq` | empty | Groq model name. |
| `LLM_TIMEOUT_SECONDS` | No | `30` (must be > 0 and ≤ 60) | Per-request LLM timeout. |
| `USE_MOCK_RAG` | No | `true` | `true` uses offline guidance fixtures; health then reports RAG as "degraded". |
| `RAG_SERVICE_URL` | When `USE_MOCK_RAG=false` | empty | Base URL of the RAG service, e.g. `http://127.0.0.1:8001` locally, `http://rag:8001` in compose and AKS. Also used by `/health`. |
| `LEASE_SECONDS` | No | `900` (minimum 600) | How long an investigation claim is held before another attempt may take over. |

`backend/.env.example` also contains `USE_MOCK_LLM`, `LLM_PROVIDER` and the
`AZURE_OPENAI_*` keys; the bridge always forces `USE_MOCK_BACKEND=false` and
`USE_MOCK_SERVICE_BUS=true` for runs inside the backend, so those two have no effect there.

!!! note "Tests force the mocks"
    `backend/tests/conftest.py` sets `USE_MOCK_LLM=true` and `USE_MOCK_RAG=true`, defaults
    `TOKEN_SECRET` and `AML_SOURCE_TIMEZONE`, and points `DATABASE_URL` at
    `TEST_DATABASE_URL`. Backend tests never call Azure, even if `.env` is configured for it.

## Agents (`agents/`)

These are the fields of `agents/config.py` (`Settings`). Names are case-insensitive.
Inside the backend, the bridge supplies `database_url`, `use_mock_backend` and
`use_mock_service_bus`; everything else comes from the environment as listed in the
[backend tables](#backend-backend).

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | No | `sqlite:///./data/synthetic_alerts.db` | **Standalone only.** Agent runtime store: a `sqlite:///` path, or a PostgreSQL URL (then schema `agent_runtime`). Not the backend's `DATABASE_URL` when running inside the backend. |
| `USE_MOCK_LLM` | No | `true` | As in the backend table. |
| `LLM_PROVIDER` | No | `azure_openai` | `azure_openai` or `groq`; any other value fails validation. |
| `AZURE_OPENAI_ENDPOINT` | When live | empty | As in the backend table. |
| `AZURE_OPENAI_DEPLOYMENT` | When live | empty | As in the backend table. |
| `AZURE_OPENAI_API_KEY` | No | empty → Entra ID | As in the backend table. Secret. |
| `AZURE_OPENAI_API_VERSION` | No | `2024-10-21` | As in the backend table. |
| `GROQ_API_KEY` / `GROQ_MODEL` | For Groq | empty | As in the backend table. |
| `USE_MOCK_RAG` | No | `true` | As in the backend table. |
| `RAG_SERVICE_URL` | When `USE_MOCK_RAG=false` | empty | Without it (and without an injected client) `create_services` raises `Configure RAG_SERVICE_URL…`. |
| `USE_MOCK_BACKEND` | No | `true` | **Standalone only.** `true` seeds synthetic alerts `ALT-001`/`ALT-002` into the SQLite store; `false` reads existing SQLite data. |
| `USE_MOCK_SERVICE_BUS` | No | `true` | `true` uses an in-process queue. `false` uses Azure Service Bus (standalone API and `agents.worker.service_bus_worker`). |
| `AZURE_SERVICE_BUS_CONNECTION_STRING` | When `USE_MOCK_SERVICE_BUS=false` | empty | Service Bus connection string. Secret. |
| `AZURE_SERVICE_BUS_QUEUE_NAME` | When `USE_MOCK_SERVICE_BUS=false` | empty | Queue name. |
| `LLM_TIMEOUT_SECONDS` | No | `30` (0 < x ≤ 60) | Per-request LLM timeout. |
| `MAX_DELIVERY_COUNT` | No | `3` (1-10) | Service Bus deliveries before dead-lettering; keep consistent with the broker. |
| `LEASE_SECONDS` | No | `900` (≥ 600) | Investigation claim lease. |
| `AML_AGENT_TEST_DATABASE_URL` | Tests only | unset → 3 tests skipped | Throwaway PostgreSQL database for `agents/tests/test_postgres_store.py`; its `agent_runtime` schema is dropped. Database name must contain `test`. |

!!! info "Service Bus is not used in the deployed system"
    Investigations run synchronously inside the backend request; health reports the queue as
    "not applicable". The Service Bus worker exists in `agents/worker/` for a future
    background-processing design.

## RAG service (`RAG/`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `RAG_BACKEND` | No | `faiss` in code; `azure` in `RAG/Dockerfile`, `RAG/.env.example` and `docker-compose.yml` | `azure` (Azure AI Search) or `faiss` (local index in `RAG/indexes/`, needs the full `requirements.txt`). Any other value stops the service at start. |
| `AZURE_SEARCH_ENDPOINT` | When `azure` | none (start fails with `KeyError`) | e.g. `https://<search-service>.search.windows.net`. |
| `AZURE_SEARCH_INDEX_NAME` | When `azure` | none | Index name; the template uses `amlens-guidance-v1`. |
| `AZURE_SEARCH_ADMIN_KEY` | No | empty → Entra ID | Search key. Despite the name, the service only queries, so a **query (read-only) key** is enough; AKS uses one. Empty uses `DefaultAzureCredential` (role *Search Index Data Reader*). Secret. The index-building scripts in `RAG/scripts/` require a real admin key. |
| `AZURE_OPENAI_BASE_URL` | When `azure` | none | Azure OpenAI v1 base URL ending in `/openai/v1/`, used for query embeddings. |
| `AZURE_OPENAI_API_KEY` | No | empty → Entra ID | Key for embeddings. Secret. |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | When `azure` | none (read at query time) | Embedding deployment; must return 1536-dimension vectors (template: `text-embedding-3-small`). |
| `AZURE_CLIENT_ID` | No | unset | Read by `azure-identity`: selects a user-assigned managed identity when keys are empty. |
| `RAG_CORS_ORIGINS` | No | unset → no CORS | Comma-separated origins for direct browser calls. Not needed with the proxy. |
| `RAG_EVAL_URL` | Script only | `http://127.0.0.1:8000/search` | Target for `RAG/scripts/evaluate_azure_rag.py`. |

`RAG/.env.example` also lists `APPROVED_AML_DOCUMENTS`; no code in `RAG/app/` or
`RAG/scripts/` reads it.

## Frontend (`frontend/`)

| Variable | Read by | Required | Default | Purpose |
|---|---|---|---|---|
| `NEXT_PUBLIC_USE_MOCKS` | Browser bundle (`lib/api/client.ts`), **build time** | No | **mock mode** in `next dev`/`next build` unless the value is exactly `false`; the Dockerfile build arg defaults to `false` (live) | Switches between built-in fixtures and live services. See [below](#next_public_use_mocks). |
| `AMLENS_BACKEND_URL` | Proxy route (`app/api/[service]/[...path]/route.ts`), runtime | In live mode | unset → `/api/backend/*` returns 404 "not configured" | Backend base URL the proxy forwards to: `http://127.0.0.1:8000` locally, `http://backend:8000` in compose and AKS. |
| `AMLENS_RAG_URL` | Proxy route, runtime | In live mode | unset → `/api/rag/*` returns 404 | RAG base URL: `http://127.0.0.1:8001` locally, `http://rag:8001` in compose and AKS. |
| `AMLENS_PROXY_KEY` | Proxy route, runtime | When the backend has `AML_PROXY_KEY` | unset → header not sent | Sent as `X-AMLens-Proxy-Key` on every forwarded request. Secret (server-side only). |
| `NEXT_PUBLIC_API_BASE_URL` | Browser bundle, build time | No | `/api/backend` | Only to bypass the proxy and call a backend directly (then the backend needs `AML_CORS_ORIGINS`). |
| `NEXT_PUBLIC_RAG_BASE_URL` | Browser bundle, build time | No | `/api/rag` | Same, for the RAG service. |
| `PORT` / `HOSTNAME` | Standalone server in the image | No | `3000` / `0.0.0.0` | Listen address of `node server.js`. |
| `NEXT_TELEMETRY_DISABLED` | Next.js | No | `1` in the image | Disables Next.js telemetry. |

The proxy also forwards the signed-in user's name to the backend as `X-AMLens-User`, taken
from the platform's auth headers (`X-MS-CLIENT-PRINCIPAL-NAME` on Container Apps,
`X-Auth-Request-Email` / `X-Auth-Request-User` from oauth2-proxy on AKS). No variable
controls this.

## Docker Compose and CI

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `AMLENS_DATABASE_URL` | Host shell, read by root `docker-compose.yml` | `postgresql+psycopg://amlens:amlens_dev@host.docker.internal:5433/amlens` | Database for the backend's `DATABASE_URL` and `AML_AGENT_DATABASE_URL` in the compose stack. |
| `AMLENS_PROXY_KEY` | Host shell, read by root `docker-compose.yml` | a fixed local placeholder | Becomes the backend's `AML_PROXY_KEY` and the frontend's `AMLENS_PROXY_KEY`. |
| `PYTHONPATH`, `TEST_DATABASE_URL`, `AML_AGENT_TEST_DATABASE_URL` | `.github/workflows/ci-cd.yml` | workspace root; `amlens_test` on the CI PostgreSQL service | See [Testing](../testing/index.md#how-ci-runs-the-tests). |
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP` | GitHub repository **variables** (not secrets; OIDC) | - | Deploy job sign-in. See [CI/CD pipeline](../deployment/ci-cd.md). |

## Key settings explained

### `AML_PROXY_KEY` and `AMLENS_PROXY_KEY`

In a deployment the browser never calls the backend directly. It calls the frontend's
`/api/backend/*` route, which sits behind sign-in and forwards the request with two headers:

| Header | Value |
|---|---|
| `X-AMLens-Proxy-Key` | The frontend's `AMLENS_PROXY_KEY` |
| `X-AMLens-User` | The signed-in user from the platform's auth headers |

The backend middleware (`app/security.py`) compares `X-AMLens-Proxy-Key` with its own
`AML_PROXY_KEY` in constant time. If they differ it returns `401 Not authenticated`; if they
match it trusts `X-AMLens-User` as the acting analyst (shown in the audit trail).
`/health` and `OPTIONS` requests are always open.

- **Same value, two names:** `AML_PROXY_KEY` on the backend, `AMLENS_PROXY_KEY` on the
  frontend. On AKS both come from the `AML_PROXY_KEY` entry of the `amlens-app` Kubernetes
  Secret; in the Container Apps design both come from the `proxy-key` secret.
- **Unset on the backend = local development:** every request is accepted and no user is
  recorded from headers.
- Use at least 32 random characters, e.g.
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

### `AMLENS_BACKEND_URL` and `AMLENS_RAG_URL`

These are read **on the frontend server at request time**, not compiled into the bundle, so
one frontend image works in every environment. The proxy maps
`/api/backend/<path>` → `AMLENS_BACKEND_URL/<path>` and `/api/rag/<path>` →
`AMLENS_RAG_URL/<path>`, re-encoding each path segment, forwarding only `Accept` and
`Content-Type` request headers, and returning `502` with "The … service is unreachable" if
the upstream cannot be reached. Because calls are same-origin, no CORS configuration is
needed. Details: [Frontend proxy](../modules/frontend-proxy.md).

### `NEXT_PUBLIC_USE_MOCKS`

!!! warning "The frontend defaults to mock mode"
    `lib/api/client.ts` uses `process.env.NEXT_PUBLIC_USE_MOCKS !== "false"`. **Unset, empty,
    `true` or any typo means mock mode**: the app shows fixtures from `lib/mocks/data.ts` and
    calls no service. Only the exact string `false` enables live services.

Because it is a `NEXT_PUBLIC_*` variable, Next.js inlines it when `next dev` starts or when
`next build` runs:

- **Local:** put `NEXT_PUBLIC_USE_MOCKS=false` in `frontend/.env.local` and restart `pnpm dev`.
- **Docker image:** it is a build argument that **defaults to `false`** (live) in
  `frontend/Dockerfile`; pass `--build-arg NEXT_PUBLIC_USE_MOCKS=true` for a self-contained
  demo image. Changing the container's environment afterwards has no effect.
- **CI** builds with `NEXT_PUBLIC_USE_MOCKS: "false"`.

The top bar shows **DEV · Mock data** or **LIVE API** so you can always tell which mode is active.

### `TOKEN_SECRET`

Account numbers are never stored. During upload, `app/utils/tokenization.py` turns each
(bank, account) pair into `ACC_` + the first 24 hex characters of an HMAC-SHA256 keyed with
`TOKEN_SECRET`. The same input and secret always give the same token, which is how account
history and alerts are linked.

!!! danger "Use the team's existing value"
    If you use a different `TOKEN_SECRET`, accounts in **new** uploads get different tokens
    from the same accounts in the **existing** data (the sample data loaded from
    `backend/aml.db` and the production database), so histories and alerts no longer line
    up. Get the value from the team; do not generate a new one unless you are creating a
    brand-new, empty environment. It must be at least 32 characters, or uploads fail with
    `Set TOKEN_SECRET to at least 32 random characters`.

`infra/deploy.ps1` reads `TOKEN_SECRET` from `backend/.env` (or `AMLENS_TOKEN_SECRET`) for
exactly this reason, and `deploy/aks/deploy.sh` stores it in the `amlens-app` Secret. To
create the very first value for a new environment:
`python -c "import secrets; print(secrets.token_hex(32))"`.

### `RUN_MIGRATIONS`

`backend/Dockerfile` sets `RUN_MIGRATIONS=true` and starts with:

```sh
if [ "$RUN_MIGRATIONS" = true ]; then alembic upgrade head; fi && exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

| Environment | Value | Who migrates |
|---|---|---|
| Local `docker compose up` | `true` (image default) | The backend container, on every start |
| AKS (`deploy/aks/base/apps.yaml`) | `false` | The `migrate` Job (`deploy/aks/jobs/migrate.yaml`), run by `rollout.sh` before the new backend |
| Container Apps design (`infra/main.bicep`) | `false` | A migrate job inside the VNet |
| Outside Docker | not read | You run `alembic upgrade head` by hand |

Set it to `false` whenever more than one replica could start at once. Because migrations
run **before** the new backend version starts, a migration must keep working with the
previous release: add columns and tables first, remove them in a later release. See
[Migrations](../database/migrations.md).

### `AML_AGENT_DATABASE_URL`

Agent runs, reports, tool calls and agent audit records are stored separately from the main
data. Locally they go to the SQLite file `AML_AGENT_DATABASE_PATH`. In any container
deployment the disk is wiped on restart, so set `AML_AGENT_DATABASE_URL` to a PostgreSQL URL
(it can be the same database as `DATABASE_URL`); the agents then create and use the schema
`agent_runtime`. Compose, AKS and the Container Apps design all do this.

## Example files

=== "backend/.env (local, live AI)"

    ```dotenv
    DATABASE_URL=postgresql+psycopg://amlens:amlens_dev@127.0.0.1:5433/amlens
    TEST_DATABASE_URL=postgresql+psycopg://amlens:amlens_dev@127.0.0.1:5433/amlens_test
    TOKEN_SECRET=<team value, at least 32 characters>
    AML_SOURCE_TIMEZONE=UTC
    AML_AGENT_DATABASE_PATH=./agent_runtime.db
    USE_MOCK_LLM=false
    LLM_PROVIDER=azure_openai
    AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
    AZURE_OPENAI_DEPLOYMENT=<chat deployment name>
    AZURE_OPENAI_API_KEY=<key, or empty for Entra ID>
    USE_MOCK_RAG=false
    RAG_SERVICE_URL=http://127.0.0.1:8001
    ```

=== "RAG/.env (Azure AI Search)"

    ```dotenv
    RAG_BACKEND=azure
    AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
    AZURE_SEARCH_ADMIN_KEY=<query or admin key, or empty for Entra ID>
    AZURE_SEARCH_INDEX_NAME=amlens-guidance-v1
    AZURE_OPENAI_BASE_URL=https://<resource>.openai.azure.com/openai/v1/
    AZURE_OPENAI_API_KEY=<key, or empty for Entra ID>
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
    ```

=== "frontend/.env.local (live services)"

    ```dotenv
    NEXT_PUBLIC_USE_MOCKS=false
    AMLENS_BACKEND_URL=http://127.0.0.1:8000
    AMLENS_RAG_URL=http://127.0.0.1:8001
    # AMLENS_PROXY_KEY=<only if backend/.env sets AML_PROXY_KEY>
    ```
