---
audience: reference
---

# Technology stack

Every technology AMLens uses, with the version declared in the repository and its role.
"Declared" versions are the constraints in `requirements*.txt`, `package.json` or Dockerfiles;
the exact version installed at image build time is the newest that satisfies the range. Where
`agents/requirements-lock.txt` records a tested exact version, it is shown in brackets.
Versions marked **verified live** were read from the production cluster on 2026-11-25.

## Runtimes and base images

| Technology | Version | Where declared | Role |
|---|---|---|---|
| Python | 3.12 (`python:3.12-slim`) | `backend/Dockerfile`, `RAG/Dockerfile`, CI | Backend, agents and RAG runtime |
| Node.js | 20 (`node:20-alpine`) | `frontend/Dockerfile`, CI | Frontend build and runtime (Next.js standalone server) |
| pnpm | 12.3.4 | `frontend/package.json` `packageManager` | Frontend package manager (via corepack) |
| PostgreSQL | 16 (`postgres:16-alpine` in AKS, verified live; `postgres:16` locally and in CI) | `deploy/aks/base/postgres.yaml`, `backend/docker-compose.yml`, CI | Main data store and agent runtime store (schema `agent_runtime`) |
| SQLite | bundled with Python | `agents/`, backend local mode | Agent store for local runs and tests; original sample database `backend/aml.db` |

## Backend (FastAPI service)

From `backend/requirements.txt`:

| Package | Version | Role |
|---|---|---|
| FastAPI | `>=0.115,<1` [0.165.0] | HTTP API framework |
| Uvicorn (`[standard]`) | `>=0.30,<1` [0.54.0] | ASGI server |
| SQLAlchemy | `>=2.0,<3` | ORM and database access |
| psycopg (`[binary]`) | `>=3.2,<4` | PostgreSQL driver |
| Alembic | `>=1.13,<2` | Schema migrations (`alembic upgrade head`) |
| pandas | `>=2.0,<3` [2.3.3] | CSV ingestion and transaction analysis |
| Pydantic | `>=2.0,<3` [2.14.3] | Request/response schemas |
| python-multipart | `>=0.0.9` | File uploads |
| python-dotenv | `>=1.0,<2` [1.2.4] | Loads `backend/.env` locally |
| httpx | `>=0.27,<1` [0.28.1] | RAG health check, tests |
| pytest | `>=8,<10` | Tests |
| azure-identity | `>=1.19,<2` [1.27.0] | Entra ID credentials (keyless Azure OpenAI) |
| azure-servicebus | `>=7.14,<8` [7.15.0] | Optional queue integration (not used in production) |

## Agents (investigation pipeline, runs inside the backend)

From `agents/requirements.txt`:

| Package | Version | Role |
|---|---|---|
| LangGraph | `>=1.0,<2` [1.2.23] | Investigation state graph (transaction → retrieval → evidence → information gap → report → verify) |
| openai | `>=1.60,<3` [2.54.0] | Azure OpenAI client (chat completions) |
| groq | `>=0.18,<2` [1.7.0] | Alternative LLM provider (`LLM_PROVIDER=groq`) |
| pydantic / pydantic-settings | `>=2.10,<3` / `>=2.7,<3` [2.14.3 / 2.16.3] | Structured outputs, settings from environment |
| psycopg | `>=3.2,<4` | PostgreSQL agent store |
| faiss-cpu | `>=1.9,<2` [1.16.0] | Installed with the agents; vector search is done by the RAG service |
| FastAPI / Uvicorn / httpx / pandas / pytest | see backend | Standalone agent API, RAG client, analysis, tests |

## RAG service

| Package | Version | Role |
|---|---|---|
| FastAPI, Uvicorn | unpinned | `/search`, `/health` API |
| Pydantic | `>=2,<3` | Models (`RetrievalResult`, `Guideline`) |
| azure-search-documents, azure-core | unpinned | Azure AI Search client |
| openai | unpinned | Embeddings via the Azure OpenAI v1 endpoint |
| azure-identity | unpinned | Keyless authentication option |
| python-dotenv | unpinned | `RAG/.env` |
| sentence-transformers (all-MiniLM-L6-v2), faiss-cpu, numpy, PyMuPDF | unpinned, `requirements.txt` only | Local FAISS mode and index-building scripts; **not** in the production image (`requirements-azure.txt`) |

## Frontend

From `frontend/package.json`:

| Package | Version | Role |
|---|---|---|
| Next.js | 14.2.35 | React framework, App Router, server-side API proxy |
| React / React DOM | ^18.3.1 | UI library |
| TypeScript | 5.7.3 | Type checking (`tsc --noEmit` in CI) |
| Tailwind CSS (+ `@tailwindcss/postcss`) | ^4.3.3 | Styling |
| shadcn / `@base-ui/react` | ^4.11.0 / ^1.5.0 | UI component primitives |
| `@tanstack/react-query` | ^5.108.2 | Data fetching and caching |
| `@tanstack/react-table` | ^8.21.3 | Alert and investigation tables |
| react-hook-form, `@hookform/resolvers`, zod | ^7.92.0, ^7.0.8, ^4.6.7 | Forms and validation |
| recharts | ^3.8.0 | Dashboard charts |
| lucide-react | ^1.16.0 | Icons |
| next-themes | ^0.4.6 | Light/dark theme |
| sonner | ^2.0.8 | Toast notifications |
| class-variance-authority, clsx, tailwind-merge, tw-animate-css | ^0.7.1, ^2.1.1, ^3.3.1, ^1.4.0 | Styling utilities |
| `@vercel/analytics` | 1.6.1 | Declared dependency; not referenced in the application code |

## Azure services

| Service | Configuration | Role |
|---|---|---|
| Azure Kubernetes Service | Kubernetes v1.36.5, 2 × Standard_B2s, Ubuntu 24.04 (verified live); Free tier, Azure CNI overlay, Cilium dataplane | Runs all workloads |
| Azure Container Registry | Basic, admin disabled | Image builds (`az acr build`) and storage, imported third-party images |
| Azure Load Balancer + public IP DNS label | `amlens-<suffix>.southindia.cloudapp.azure.com` | Public entry point |
| Azure Managed Disk | 8 Gi, `managed-csi` (verified live) | PostgreSQL data volume |
| Azure Blob Storage | Standard_LRS, container `pg-backups`, 14-day lifecycle | Database backups |
| Azure OpenAI | `gpt-4.1-mini` (chat), `text-embedding-3-small` (embeddings) (verified live) | Report narrative, query and document embeddings |
| Azure AI Search | index `amlens-guidance-v1`, HNSW cosine, 1536 dims (verified live: index name) | Guidance retrieval |
| Microsoft Entra ID | App registration created by `deploy.sh`, not active; OIDC federation for CI | Future sign-in; pipeline authentication |

Designed but not deployed ([Container Apps design](../developer-guide/deployment/container-apps-design.md)):
Azure Container Apps, Azure Database for PostgreSQL Flexible Server (B1ms), Key Vault, Log
Analytics, user-assigned managed identities, Bicep.

## Cluster add-ons and edge

| Technology | Version | Role |
|---|---|---|
| AKS application routing (managed NGINX ingress) | managed by AKS | Ingress controller `amlens-nginx` (verified live) |
| cert-manager | v1.16.2 (verified live) | Let's Encrypt certificates (HTTP-01) |
| Let's Encrypt | ACME v2 production | TLS certificate for the public host |
| oauth2-proxy | v7.7.1 (verified live) | Sign-in (htpasswd form) and auth subrequests |
| Cilium | managed by AKS (verified live) | Network dataplane, NetworkPolicy enforcement |
| curl | `curlimages/curl:8.11.0` (verified live) | Uploads backups to Blob Storage |

## Tooling, CI and documentation

| Technology | Version | Role |
|---|---|---|
| GitHub Actions | `actions/checkout@v4`, `setup-python@v5`, `setup-node@v4`, `pnpm/action-setup@v4`, `azure/login@v2`, `azure/setup-kubectl@v4` | CI/CD |
| Azure CLI | current | `deploy.sh`, `rollout.sh`, `infra/deploy.ps1` |
| kubectl | installed by `az aks install-cli` if missing | Cluster operations |
| Bash (Git Bash on Windows) | — | Deployment scripts |
| PowerShell | — | `infra/deploy.ps1` |
| Bicep | — | `infra/main.bicep` (Container Apps design) |
| Docker / Docker Compose | — | Local PostgreSQL and production-like local run |
| bcrypt (Python) | latest at run time | Password hashes in `add-user.sh` |
| MkDocs / Material for MkDocs / pymdown-extensions | 1.6.1 / 9.5.49 / 10.21.3 | This documentation site (`docs/requirements.txt`) |
