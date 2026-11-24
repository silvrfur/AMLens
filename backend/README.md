# AML Member 1 local backend starter

This is a **development MVP starter**, not a production-ready AML platform. It was written to match the 11 columns identified in the supplied HI-Small EDA.

## Where data lives

| Data | Store | Owner |
|---|---|---|
| Transactions, alerts, investigations, decisions, audit history | **PostgreSQL** (`DATABASE_URL`) | this backend |
| Agent runtime (AI reports, agent runs, tool calls) | SQLite `agent_runtime.db` (git-ignored, created on first run) | `agents` package |

The agents read the main data only through `app/integrations/team_backend.py`
(`get_alert_context` → `AlertBundle`), inside PostgreSQL `READ ONLY` transactions.
Tables are created/changed only by **Alembic** migrations (`alembic/versions/`);
the app refuses to start against an un-migrated database.

## Setup from scratch (Windows PowerShell, Docker)

> To run the whole stack (backend + agents + RAG + frontend), follow the root
> `README.md`. The steps below set up and test this backend on its own.

You need **Docker Desktop**, **Python 3.11+** and **Git**. No PostgreSQL install and no
database admin password are needed - Docker provides a ready-made database.
Commands assume PowerShell; macOS/Linux equivalents are in comments.

### 1. Get the code

```powershell
git clone https://github.com/silvrfur/AMLens.git
cd AMLens
git checkout integration
cd backend
```

### 2. Start the database

Start **Docker Desktop** and wait for "Engine running", then:

```powershell
docker compose up -d
docker compose ps          # STATUS should show "healthy" after ~10 s
```

This runs PostgreSQL 16 on **127.0.0.1:5433** with user `amlens` / password `amlens_dev`
and two databases: `amlens` (app) and `amlens_test` (wiped by tests). Dev-only credentials.

### 3. Python environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

If activation says "running scripts is disabled": `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.

### 4. Settings file

```powershell
copy .env.example .env               # macOS/Linux: cp .env.example .env
notepad .env
```

The defaults already point at the Docker database. You only need to set:

- `TOKEN_SECRET` - **ask the team for the shared value** (shared privately, never in git).
  Everyone must use the same one, otherwise the same bank account gets a different token
  on each machine. To create the very first one: `python -c "import secrets; print(secrets.token_hex(32))"`.
- For live AI and guidance instead of the mocks, see the settings table in the root `README.md`.

`.env` is git-ignored. Use `127.0.0.1` rather than `localhost` in database URLs: on Windows
`localhost` may try IPv6 first, which Docker doesn't listen on, causing long stalls.

### 5. Create the tables

```powershell
alembic upgrade head                 # last line: "Running upgrade -> 0001_initial"
```

Optional - load the sample data from the old SQLite file (`aml.db` in this folder):

```powershell
python scripts/migrate_sqlite_to_postgres.py   # copies ./aml.db, never modifies it
python scripts/check_alerts.py                 # expect 46/47 OK (one legacy alert has no created_at)
```

The copy runs in one transaction, keeps all IDs, refuses a non-empty target and verifies row counts.

### 6. Make the agents package importable (needed for tests and AI runs)

The backend imports the `agents` package from the `agents/` folder at the repository root.
From `backend/`:

```powershell
pip install -r ..\agents\requirements.txt
$env:PYTHONPATH = (Resolve-Path ..).Path    # repeat in every new terminal
```

### 7. Run the tests

```powershell
pytest -q                            # expect: 17 passed
```

`TEST_DATABASE_URL` comes from `.env`. Database tests are skipped without it, API/adapter tests are
skipped without the `agents` package (step 6) - "skipped" means one of those is missing.

### 8. Run the app

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs. Quick check: upload `examples/demo_transactions_v2.csv` via
`POST /upload-transactions` (expect `accepted: 3`), then `GET /alerts`.
Full flow: `POST /investigate/{alert_id}` → `POST /investigations/{id}/run` →
`GET /investigations/{id}/report` → `POST /investigations/{id}/decision` → `GET /audit/{id}`.

For the frontend, add `AML_CORS_ORIGINS=http://localhost:3000` to `.env`.

### Everyday use

```powershell
cd backend
docker compose up -d                 # start the database (data is kept)
.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Resolve-Path ..).Path
uvicorn app.main:app --reload
docker compose stop                  # when done
```

After pulling changes that add a file under `alembic/versions/`, run `alembic upgrade head` again
(the app refuses to start otherwise and tells you so).
`docker compose down -v` **deletes all data** for a clean start (then `alembic upgrade head` again).

### Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: ... cannot connect` | Docker Desktop is not running yet - start it and wait |
| `relation "alerts" does not exist` / "schema is not up to date" | `alembic upgrade head` |
| Tests or app hang ~8 s+ on every DB call | Use `127.0.0.1`, not `localhost`, in `.env` |
| `DATABASE_URL is not set` | Run from `backend/`, and create `.env` (step 4) |
| `No module named 'agents'` | Set `PYTHONPATH` (step 6) in this terminal |
| Port 5433 already in use | Change `127.0.0.1:5433` in `docker-compose.yml` and both URLs in `.env` |

### Alternative: locally installed PostgreSQL 16

Instead of Docker, using the admin password chosen at install time:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h 127.0.0.1 -c "CREATE ROLE amlens LOGIN PASSWORD 'amlens_dev' CREATEDB;" -c "CREATE DATABASE amlens OWNER amlens;" -c "CREATE DATABASE amlens_test OWNER amlens;"
```

Then use port `5432` instead of `5433` in both URLs in `.env`.

### Helper scripts

- `scripts/inspect_db.py` - read-only table viewer / ad-hoc SELECTs
- `scripts/check_alerts.py` - verify every alert converts to an AlertBundle
- `scripts/create_readonly_role.sql` - optional SELECT-only login for the agents (`AML_SOURCE_DATABASE_URL`)
- `phase4_run.py [ALERT_ID]` - run one alert through the agents (mock LLM/RAG)

Deploying the database to Azure: see [DEPLOY_AZURE.md](DEPLOY_AZURE.md).

## First upload

Use Swagger `POST /upload-transactions` to upload an IBM CSV subset (max 20 MB, 100,000 rows). The starter doesn't save the uploaded raw CSV or labels; you must add separate restricted storage before evaluation.

The first CSV line is the header, so the first transaction has `source_row=2`. The dataset hash is derived from raw upload bytes, and IDs follow `TX_<dataset_id>_<source_row>`.

## APIs

- POST `/upload-transactions`
- GET `/alerts`, `/alerts/{alert_id}`
- GET `/accounts/{account_id}/history` (use account token)
- POST `/investigate/{alert_id}`
- POST `/investigations/{id}/run` (dev only: synchronous agent run, mock LLM/RAG)
- GET `/investigations/{id}`, `/investigations/{id}/report`
- POST `/investigations/{id}/decision`
- GET `/audit/{id}`

## Current rule examples

- `HIGH_VALUE`: explicit **US Dollar** threshold of 1,000,000, configurable in code; not a universal AML threshold.
- `REPEATED_PAIR`: >=5 transactions for a directed pair and payment currency in one uploaded batch.
- `RAPID_MOVEMENT_CANDIDATE`: transactions with matching intermediary account and currency, strictly increasing timestamps, within 60 minutes. Does NOT prove identical funds or account-level net flows.

## Important security and scale limits

- There is **no authentication/authorization** yet. Do not expose the app to the internet or use real customer data.
- `TOKEN_SECRET` must remain secure and unchanged for repeat token stability; production should use managed secret storage and more restricted mapping practices.
- Upload validation uses Pandas row loops and in-memory analysis: limit is 100k rows / 20MB; large batches and graph join detection need chunking, indexing, and background jobs before full 5M row ingestion.
- Ground truth is parsed for validity, then discarded. No agent or alert endpoint receives `Is Laundering`. For offline evaluation, separately persist labels in an **isolated evaluation datastore** keyed by stable transaction ID with restricted access.
- Raw file storage, processed-file exports, Azure Blob SDK integration, Entra ID (managed identity) database login, role-based access, tamper-evident audit records, and agent-generated report exports are **not implemented** yet.
- Audit events are append-only by convention only; enforce immutability with database permissions and integrity controls before production.
- Monetary storage uses SQLAlchemy `Numeric`; rule thresholds are exploratory and currency-specific.
- The API returns up to 50 rejection reasons, with total rejection count and truncation flag.
- Tests use a real throwaway PostgreSQL database (`TEST_DATABASE_URL`) with fixtures in `tests/conftest.py`.

## Next steps

1. Implement structured rejection export with original source-row refs.
2. Add `account_tokens` mapping table only in a restricted data boundary if reversibility is required; HMAC is irreversible but stable.
3. Improve rule engine for frequency, per-currency totals, longer multi-hop paths, and graph networks.
4. Add Azure Blob raw/processed artifacts, using `DefaultAzureCredential` where appropriate.
5. Deploy PostgreSQL to Azure Database for PostgreSQL Flexible Server (DEPLOY_AZURE.md) and switch to Microsoft Entra authentication.
6. Harden access controls, operational logs, deterministic idempotency and audit integrity.
