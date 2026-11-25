---
audience: reference
---

# Supported platforms

This page lists the runtimes, operating systems, browsers and cloud services AMLens is built,
tested and deployed on. "Supported" means the version the project's Docker images and CI
pipeline use; other versions may work but are not checked by CI.

## Runtime versions

| Component | Supported | Also documented | Where it is pinned |
|---|---|---|---|
| Python (backend, agents, RAG) | **3.12** | 3.11+ in the root and backend READMEs | `FROM python:3.12-slim` in `backend/Dockerfile`, `RAG/Dockerfile`; `python-version: "3.12"` in `.github/workflows/ci-cd.yml` |
| Node.js (frontend) | **20** | 18+ in the root README (Next.js 14 needs 18.17 or later) | `FROM node:20-alpine` in `frontend/Dockerfile`; `node-version: "20"` in CI |
| pnpm | **12.3.4** | - | `"packageManager": "pnpm@12.3.4"` in `frontend/package.json`; CI's `pnpm/action-setup` reads it |
| PostgreSQL | **16** | - | `image: postgres:16` in `backend/docker-compose.yml` and CI; `postgres:16-alpine` in the AKS StatefulSet |
| SQLite | Bundled with Python | - | Agent runtime store for local development and tests only |

!!! note "Observed beyond the supported versions"
    While writing this documentation, the agent test suite passed (95 passed, 3 skipped) on
    **Python 3.14.8** and the frontend type-check passed on **Node.js 24.21**. These are
    observations from one Windows machine, not supported configurations.

## Key frameworks and libraries

| Component | Framework | Version constraint | Source |
|---|---|---|---|
| Backend | FastAPI | `>=0.115,<1` | `backend/requirements.txt` |
| Backend | SQLAlchemy | `>=2.0,<3` | `backend/requirements.txt` |
| Backend | Alembic | `>=1.13,<2` | `backend/requirements.txt` |
| Backend, agents | psycopg (v3, binary) | `>=3.2,<4` | `backend/requirements.txt`, `agents/requirements.txt` |
| Backend, agents | pandas | `>=2.0,<3` / `>=2.2,<3` | requirements files |
| Agents | LangGraph | `>=1.0,<2` | `agents/requirements.txt` |
| Agents | OpenAI SDK (Azure OpenAI) | `>=1.60,<3` | `agents/requirements.txt` |
| Agents | Groq SDK | `>=0.18,<2` | `agents/requirements.txt` |
| Agents | pydantic / pydantic-settings | `>=2.10,<3` / `>=2.7,<3` | `agents/requirements.txt` |
| RAG | FastAPI, azure-search-documents, openai, azure-identity | unpinned | `RAG/requirements-azure.txt` |
| RAG (local FAISS mode) | sentence-transformers (`all-MiniLM-L6-v2`), faiss-cpu | unpinned | `RAG/requirements.txt` |
| Frontend | Next.js | `14.2.35` (exact) | `frontend/package.json` |
| Frontend | React / React DOM | `^18.3.1` | `frontend/package.json` |
| Frontend | TypeScript | `5.7.3` (exact) | `frontend/package.json` |
| Frontend | Tailwind CSS | `^4.3.3` | `frontend/package.json` |
| Documentation | MkDocs / Material | `1.6.1` / `9.5.49` | `docs/requirements.txt` |

`agents/requirements-lock.txt` records an exact, tested set of versions for the agents
package. The frontend's exact dependency tree is fixed by `frontend/pnpm-lock.yaml`
(installed with `--frozen-lockfile` in CI and the image).

## Development operating systems

| OS | Status | Notes |
|---|---|---|
| **Windows 10/11 and Windows Server** (PowerShell) | Supported for development | The root and backend READMEs are written for PowerShell. Use `127.0.0.1` rather than `localhost` in database URLs. See [Common setup issues](../developer-guide/getting-started/local-development.md#common-setup-issues). |
| **Linux** | Supported for development; CI runs on `ubuntu-latest` | Bash equivalents are given throughout the developer guide. |
| **macOS** | Expected to work, not verified | Same commands as Linux. The Docker images are Linux images. |

| Tool | Requirement |
|---|---|
| Docker | Docker Desktop (Windows/macOS) or Docker Engine with Compose v2 (`docker compose`) |
| Bash | Required only for the deployment scripts (`deploy/aks/*.sh`, `infra/seed/*.sh`); on Windows use Git Bash |
| Azure CLI | Required only for deployment |

## Container images

| Image | Base | Port | Runs as |
|---|---|---|---|
| `amlens-backend` (backend + agents) | `python:3.12-slim` | 8000 | UID 1001 (`app`) |
| `amlens-rag` | `python:3.12-slim` | 8001 | UID 1001 (`app`) |
| `amlens-frontend` | `node:20-alpine` (Next.js standalone output) | 3000 | UID 1001 (`nextjs`) |
| PostgreSQL | `postgres:16` (local, CI); `postgres:16-alpine` (AKS) | 5432 | image default |

All images are built for Linux. The RAG image installs only `requirements-azure.txt` by
default; build with `--build-arg RAG_REQUIREMENTS=requirements.txt` for the FAISS backend.

## Browsers

The repository does not define a browser support list (no `browserslist` in
`frontend/package.json`) and has no browser tests, so the frontend targets **Next.js 14's
default browser support**: current versions of Chrome, Edge, Firefox and Safari.
**Recommendation:** use a current Chromium-based browser or Firefox; other browsers are not
tested.

## Cloud platforms

| Service | Use | Status |
|---|---|---|
| **Azure Kubernetes Service (AKS)** | Live deployment: 2 × `Standard_B2s` nodes, Azure CNI overlay with Cilium, app-routing NGINX ingress, cert-manager (Let's Encrypt), oauth2-proxy sign-in, region `southindia` | **Current production** |
| **Azure Container Apps** | Alternative design in `infra/main.bicep` (VNet, Key Vault, PostgreSQL Flexible Server, Entra ID sign-in) | Designed for an unrestricted subscription; not the live deployment |
| **Azure Container Registry** | Image registry (images tagged with the commit SHA) | Used by both designs |
| **Azure OpenAI** | Chat completions for the report agent (deployment must support JSON mode, e.g. gpt-4o / gpt-4.1 family); embeddings for RAG queries (1536-dimension model such as `text-embedding-3-small`) | Required for live AI; optional locally (mock LLM) |
| **Azure AI Search** | Vector search over approved guidance (`RAG_BACKEND=azure`) | Required for live guidance in production; locally FAISS or mock RAG can stand in |
| **Groq** | Alternative LLM provider (`LLM_PROVIDER=groq`) | Supported by the agents; not used in the deployment |
| **Azure Service Bus** | Queue for a background worker (`agents/worker/`) | Implemented and contract-tested; **not used** in the deployment (runs are in-process) |
| **Azure Blob Storage** | Nightly `pg_dump` backups on AKS | Used by the AKS deployment |
| **GitHub Actions** | CI/CD with OIDC sign-in to Azure | Current pipeline |

Details: [Production environment](../developer-guide/deployment/index.md),
[AKS deployment](../developer-guide/deployment/aks-deployment.md),
[Container Apps design](../developer-guide/deployment/container-apps-design.md),
[Technology stack](technology-stack.md).
