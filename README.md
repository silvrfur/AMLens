# AMLens

AI-assisted review workspace for transaction-monitoring alerts. Four parts, one per team member:

| Folder | What it is | Port |
|---|---|---|
| `backend/` | FastAPI + PostgreSQL: uploads, alerts, investigations, decisions, audit | 8000 |
| `agents/` | LangGraph investigation agents (imported by the backend, not a server) | - |
| `RAG/` | AML guidance retrieval (Azure AI Search, or local FAISS) | 8001 |
| `frontend/` | Next.js analyst workspace | 3000 |

## Running the full stack (Windows PowerShell)

You need Docker Desktop, Python 3.11+, Node.js 18+ and Git.
Every block below starts from the repository root.

### One-time setup

```powershell
git clone https://github.com/silvrfur/AMLens.git
cd AMLens
git checkout integration

# Database (PostgreSQL 16 on 127.0.0.1:5433)
cd backend; docker compose up -d; cd ..

# Backend + agents share one environment at the repo root
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt -r agents\requirements.txt

# RAG has its own environment (it needs sentence-transformers / faiss)
python -m venv RAG\.venv
RAG\.venv\Scripts\python -m pip install -r RAG\requirements.txt

# Frontend
cd frontend; npx pnpm install; cd ..
```

### Settings files (never commit these)

| File | Start from | Must set |
|---|---|---|
| `backend\.env` | `backend\.env.example` | `TOKEN_SECRET` (shared team value). Live AI: `USE_MOCK_LLM=false`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY`. Live guidance: `USE_MOCK_RAG=false`, `RAG_SERVICE_URL=http://127.0.0.1:8001`. Browser access: `AML_CORS_ORIGINS=http://localhost:3000` |
| `RAG\.env` | `RAG\.env.example` | `RAG_BACKEND=azure`, the `AZURE_SEARCH_*` and `AZURE_OPENAI_*` values, `RAG_CORS_ORIGINS=http://localhost:3000` |
| `frontend\.env.local` | (new file) | `NEXT_PUBLIC_USE_MOCKS=false`, `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`, `NEXT_PUBLIC_RAG_BASE_URL=http://localhost:8001` |

Without `frontend\.env.local` the frontend shows built-in mock data and calls no service.
Ask the team for the Azure keys and `TOKEN_SECRET`; they are shared privately, never in git.

Then create the tables and load the sample data (first time only):

```powershell
$env:PYTHONPATH = (Get-Location).Path
cd backend
..\.venv\Scripts\alembic upgrade head
..\.venv\Scripts\python scripts\migrate_sqlite_to_postgres.py
cd ..
```

### Start everything (three terminals)

```powershell
# Terminal 1 - RAG service
cd RAG
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

```powershell
# Terminal 2 - backend (PYTHONPATH lets it import the agents package)
$env:PYTHONPATH = (Get-Location).Path
cd backend
docker compose up -d
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 3 - frontend
cd frontend
npx pnpm dev
```

Open http://localhost:3000. Settings > Service health should show the backend, agent and
RAG service as healthy, and the task queue as "not applicable" (runs execute in-process).

### Before a demo

- Click through every page once: the dev server compiles each page on its first visit.
- If Azure is unreachable, set `USE_MOCK_RAG=true` (and/or `USE_MOCK_LLM=true`) in
  `backend\.env` and restart the backend; investigations then use offline fixtures.

### Tests

```powershell
$env:PYTHONPATH = (Get-Location).Path
.venv\Scripts\python -m pytest agents\tests -q              # agents
cd backend; ..\.venv\Scripts\python -m pytest -q; cd ..     # backend (needs the Docker database)
cd frontend; npx tsc --noEmit; cd ..                        # frontend type-check
```

Backend tests always use the mock LLM and mock RAG, so they never call Azure.

See `backend/README.md` and `RAG/README.md` for details on each service.
