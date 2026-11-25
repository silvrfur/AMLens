---
audience: developer
---

# System architecture

This page describes AMLens at three zoom levels (system context, containers, components) and
then follows one investigation request end to end. All facts are taken from the code and the
manifests in `deploy/aks/base/`; anything inferred is marked **Inferred**.

## System context

```mermaid
flowchart TB
    analyst["AML analyst"]
    admin["Operator<br/>deploy.sh, kubectl"]
    amlens["AMLens<br/>alert investigation workspace"]
    idp["Sign-in<br/>oauth2-proxy: htpasswd accounts,<br/>Entra ID OIDC configured"]
    aoai["Azure OpenAI<br/>chat deployment + text-embedding-3-small"]
    search["Azure AI Search<br/>AML guidance index"]
    blob["Azure Blob Storage<br/>nightly pg_dump"]
    acr["Azure Container Registry"]

    analyst -->|"HTTPS, browser"| idp
    idp -->|"authenticated requests"| amlens
    admin -->|"images, manifests"| acr
    acr --> amlens
    amlens -->|"report narrative selection"| aoai
    amlens -->|"query embeddings"| aoai
    amlens -->|"vector search"| search
    amlens -->|"write-only SAS upload"| blob
```

| External system | Used by | Purpose | Auth in the AKS deployment |
|---|---|---|---|
| Azure OpenAI (chat) | Backend (agents `AzureOpenAILLM`) | Report agent selects and orders approved statements | API key (`amlens-ai` secret); Entra ID token provider when no key is set |
| Azure OpenAI (embeddings) | RAG `TeamAzureSearchAdapter` | Embeds the search query (1536 dimensions) | API key or `DefaultAzureCredential` |
| Azure AI Search | RAG | Vector search with typology pre-filter | Query key, or `DefaultAzureCredential` |
| Azure Blob Storage | `postgres-backup` CronJob | Off-cluster logical backups | Write-only SAS |
| oauth2-proxy | Ingress | Sign-in; sets `X-Auth-Request-User` / `X-Auth-Request-Email` | htpasswd file (bcrypt) plus OIDC client |

## Containers

```mermaid
flowchart LR
    browser["Browser"]
    subgraph edgeLayer["Edge (namespace amlens + app-routing-system)"]
        nginx["NGINX ingress<br/>app routing add-on, TLS"]
        o2p["oauth2-proxy<br/>:4180"]
    end
    subgraph appLayer["Application pods"]
        fe["frontend<br/>Next.js :3000"]
        be["backend<br/>FastAPI :8000<br/>+ agents package"]
        rag["rag<br/>FastAPI :8001"]
    end
    subgraph dataLayer["Data"]
        pg[("postgres<br/>StatefulSet, PG 16<br/>8 Gi managed disk")]
        cron["postgres-backup<br/>CronJob 20:30 UTC"]
        mig["migrate Job<br/>alembic upgrade head"]
    end
    aoai["Azure OpenAI"]
    ais["Azure AI Search"]
    blob["Blob Storage"]

    browser --> nginx
    nginx -->|"auth-url subrequest"| o2p
    nginx -->|"/"| fe
    nginx -->|"/oauth2"| o2p
    fe -->|"/api/backend/*"| be
    fe -->|"/api/rag/*"| rag
    be -->|"SQL"| pg
    be -->|"POST /search"| rag
    be --> aoai
    rag --> aoai
    rag --> ais
    mig --> pg
    cron --> pg
    cron --> blob
```

### Container reference

| Container | Image / source | Port | Talks to | Allowed inbound (NetworkPolicy) |
|---|---|---|---|---|
| `frontend` | `frontend/Dockerfile` (Node 20 alpine, `output: "standalone"`) | 3000 | backend, rag | ingress controller namespace `app-routing-system` |
| `oauth2-proxy` | `oauth2-proxy/oauth2-proxy:v7.7.1` (imported to ACR) | 4180 | Entra ID OIDC | ingress controller |
| `backend` | `backend/Dockerfile`, built from repo root; contains `backend/app`, `backend/alembic`, `agents/` | 8000 | postgres, rag, Azure OpenAI | `app: frontend` only |
| `rag` | `RAG/Dockerfile`, default `requirements-azure.txt` (no torch/FAISS) | 8001 | Azure OpenAI, Azure AI Search | `app: backend`, `app: frontend` |
| `postgres` | `postgres:16-alpine` StatefulSet, PVC `managed-csi` 8 Gi | 5432 | none | pods labelled `amlens.io/db-client: "true"` (backend, migrate, seed, backup) |
| `migrate` Job | backend image, `alembic upgrade head` | none | postgres | none |
| `postgres-backup` CronJob | `pg_dump -Fc` then `curl PUT` to Blob | none | postgres, Blob | none |

The namespace starts from `default-deny-ingress`; each allow rule is in
`deploy/aks/base/network-policy.yaml`. Outbound traffic is not restricted.

### Ingress routes

| Ingress | Path | Backend | Auth |
|---|---|---|---|
| `amlens-web` | `/` (prefix) | `frontend:3000` | `auth-url` → oauth2-proxy `/oauth2/auth`; copies `X-Auth-Request-Email,X-Auth-Request-User` |
| `amlens-oauth2` | `/oauth2` | `oauth2-proxy:4180` | none; rate limited `limit-rpm: "20"` |
| `amlens-health` | `/api/backend/health` (exact) | `frontend:3000` | none (status only, for smoke tests) |

`amlens-web` also sets `proxy-body-size: "25m"` (CSV uploads) and `proxy-read-timeout: "300"`
(investigations run in the request).

## Components inside the backend container

```mermaid
flowchart TB
    subgraph proc["uvicorn process: app.main:app"]
        mw["require_proxy middleware<br/>app/security.py"]
        cors["CORSMiddleware<br/>only if AML_CORS_ORIGINS"]
        routers["Routers<br/>upload, alerts, transactions,<br/>investigations, health"]
        ingest["services/ingestion.py<br/>services/validation.py"]
        rules["services/transaction_analysis.py<br/>generate_findings"]
        token["utils/tokenization.py<br/>account_token"]
        bridge["services/agent_bridge.py"]
        tb["integrations/team_backend.py<br/>TeamBackend"]
        subgraph agentspkg["agents package"]
            runner["graph.py<br/>InvestigationRunner"]
            nodes["agents/*.py<br/>verifier/report_verifier.py"]
            store["services/postgres_service.py<br/>or sqlite_service.py"]
            llm["services/azure_openai_llm.py<br/>groq_llm.py, mocks"]
            ragc["services/rag_client.py<br/>HTTPRAGClient"]
        end
        orm["database/connection.py, tables.py<br/>SQLAlchemy"]
    end

    cors --> mw --> routers
    routers --> ingest --> token
    ingest --> rules
    routers --> orm
    routers --> bridge --> runner
    bridge --> tb
    runner --> nodes
    nodes --> tb
    nodes --> ragc
    nodes --> llm
    runner --> store
```

## Request lifecycle: running an investigation

The sequence below is what happens when an analyst clicks **Run investigation** on an alert in
the AKS deployment (`USE_MOCK_LLM=false`, `USE_MOCK_RAG=false`).

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant N as NGINX ingress
    participant O as oauth2-proxy
    participant F as Next.js proxy route
    participant API as Backend FastAPI
    participant G as InvestigationRunner
    participant PG as PostgreSQL
    participant R as RAG service
    participant AI as Azure OpenAI
    participant S as Azure AI Search

    B->>N: POST /api/backend/investigate/{alert_id}
    N->>O: GET /oauth2/auth (cookie)
    O-->>N: 202 + X-Auth-Request-User
    N->>F: request + X-Auth-Request-User
    F->>API: POST /investigate/{alert_id}<br/>X-AMLens-Proxy-Key, X-AMLens-User
    API->>PG: INSERT investigations PENDING_AGENT,<br/>audit_history CREATED, alert UNDER REVIEW
    API-->>B: 201 investigation_id
    B->>N: POST /api/backend/investigations/{id}/run
    N->>F: (same auth subrequest)
    F->>API: POST /investigations/{id}/run
    API->>PG: status RUNNING, audit AGENT_RUN_REQUESTED
    API->>G: runner.run(InvestigationMessage)
    G->>PG: claim lease in agent_runtime.investigations
    G->>PG: transaction node: READ ONLY alert + 48h history
    G->>R: retrieval node: POST /search (1-2 queries)
    R->>AI: embeddings.create
    R->>S: vector search, filter typology eq ...
    S-->>R: hits
    R-->>G: RetrievalResult (score >= 0.40)
    G->>AI: report node: chat.completions JSON mode
    AI-->>G: NarrativeDraft
    G->>G: verify node: ReportVerifier recomputes report
    G->>PG: persist: report_json, verification_json, audit_log
    G-->>API: persisted record
    API->>PG: status COMPLETED or INCOMPLETE,<br/>audit AGENT_RUN_FINISHED
    API-->>B: execution_status, report_available
    B->>F: GET /api/backend/investigations/{id}/report
    F->>API: GET /investigations/{id}/report
    API->>PG: read agent_runtime record
    API-->>B: report, verification, agent_execution_trace
```

Notes on the lifecycle:

- Steps 2 to 4 repeat on every request: NGINX calls oauth2-proxy's `/oauth2/auth` for each
  request to `amlens-web`. Unauthenticated users are redirected to `/oauth2/sign_in`.
- The proxy forwards only `accept` and `content-type` from the browser, plus the two
  `X-AMLens-*` headers. Cookies never reach the backend.
- The browser makes three separate calls (`investigate`, `run`, `report`). The first is
  skipped when an investigation for the alert is already `pending` or `running`
  (`components/pages/alert-detail.tsx`).
- The run call holds the HTTP connection for the whole pipeline. Every agent node writes an
  `agent_runs` row and every external call writes a `tool_calls` row, so a run can be
  inspected after the fact even if the client disconnects.

## Topologies

| Environment | How it runs | Agent store | LLM / RAG |
|---|---|---|---|
| Local dev (`uvicorn` + `pnpm dev`) | Processes on the host; `backend/docker-compose.yml` for PostgreSQL | SQLite `./agent_runtime.db` unless `AML_AGENT_DATABASE_URL` is set | Mocks by default (`USE_MOCK_LLM`, `USE_MOCK_RAG` default `true`) |
| Root `docker-compose.yml` | Three images; only frontend published on `127.0.0.1:3100` | PostgreSQL, schema `agent_runtime` | From `backend/.env` and `RAG/.env` |
| AKS (live) | `deploy/aks/base/*.yaml`, one replica each | PostgreSQL StatefulSet, schema `agent_runtime` | Azure OpenAI (`LLM_PROVIDER=azure_openai`), RAG with `RAG_BACKEND=azure` |
| Container Apps (`infra/`) | Alternative design for an unrestricted subscription | PostgreSQL Flexible Server | Managed identity |

See [AKS deployment](../deployment/aks-deployment.md) and
[Container Apps design](../deployment/container-apps-design.md) for the operational detail.

## Scaling characteristics

| Concern | Current behaviour |
|---|---|
| Replicas | 1 for every Deployment. The agent store is in PostgreSQL with advisory locks and leases, so more backend replicas are safe for correctness. |
| Long runs | Bound by the ingress `proxy-read-timeout` (300 s) and by the LLM timeout (`llm_timeout_seconds`, default 30 s, max 3 attempts per call). |
| Concurrency on one investigation | `Persistence.claim()` takes `pg_advisory_xact_lock(hashtext(investigation_id))`; a second run while the lease is live raises `InvestigationBusy` and the backend returns 409. |
| Database connections | Backend pool: `DB_POOL_SIZE` 5 + `DB_MAX_OVERFLOW` 10. `TeamBackend` keeps its own pool (2 + 2). The agent store opens a new psycopg connection per operation (no pool). |

## Related pages

- [Backend architecture](backend-architecture.md)
- [Frontend proxy](../modules/frontend-proxy.md)
- [Authentication](../authentication/index.md)
- [Security](../security/index.md)
