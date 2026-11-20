# AML Member 1 local backend starter

This is a **development MVP starter**, not a production-ready AML platform. It was written to match the 11 columns identified in the supplied HI-Small EDA.

## Quick start

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Set this in your shell BEFORE starting the server:
# macOS/Linux: export TOKEN_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
# Windows PowerShell: $env:TOKEN_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs or GET /health.

## First upload

Use Swagger `POST /upload-transactions` to upload an IBM CSV subset (max 20 MB, 100,000 rows). The starter doesn't save the uploaded raw CSV or labels; you must add separate restricted storage before evaluation.

The first CSV line is the header, so the first transaction has `source_row=2`. The dataset hash is derived from raw upload bytes, and IDs follow `TX_<dataset_id>_<source_row>`.

## APIs

- POST `/upload-transactions`
- GET `/alerts`, `/alerts/{alert_id}`
- GET `/accounts/{account_id}/history` (use account token)
- POST `/investigate/{alert_id}`
- GET `/investigations/{id}`
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
- Raw file storage, processed-file exports, Azure Blob SDK integration, Azure SQL driver + managed identity, Alembic migrations, role-based access, tamper-evident audit records, and agent-generated report exports are **not implemented** yet.
- Audit events are append-only by convention only; enforce immutability with database permissions and integrity controls before production.
- Monetary storage uses SQLAlchemy `Numeric`; rule thresholds are exploratory and currency-specific.
- The API returns up to 50 rejection reasons, with total rejection count and truncation flag.
- The sample `test_api.py` uses a special SQLite in-memory setup. For further tests, prefer dependency-overridden database sessions and isolated fixtures.

## Next steps

1. Implement structured rejection export with original source-row refs.
2. Add `account_tokens` mapping table only in a restricted data boundary if reversibility is required; HMAC is irreversible but stable.
3. Improve rule engine for frequency, per-currency totals, longer multi-hop paths, and graph networks.
4. Add Azure Blob raw/processed artifacts, using `DefaultAzureCredential` where appropriate.
5. Add Azure SQL through SQLAlchemy + `pyodbc`, Microsoft Entra authentication, and Alembic migrations.
6. Harden access controls, operational logs, deterministic idempotency and audit integrity.
