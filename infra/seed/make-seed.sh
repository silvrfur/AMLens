#!/usr/bin/env bash
# Builds infra/seed/seed.sql (data only) from the team's committed backend/aml.db, using the
# local docker PostgreSQL (backend/docker-compose.yml) as scratch space. Run from the repo root:
#   bash infra/seed/make-seed.sh
# Needs: docker, and the backend venv (backend/.venv or .venv) for alembic + the copy script.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/backend/.venv/Scripts/python"; [ -x "$PY" ] || PY="$ROOT/.venv/Scripts/python"; [ -x "$PY" ] || PY="$ROOT/.venv/bin/python"
PG="docker compose -f $ROOT/backend/docker-compose.yml exec -T postgres"
SCRATCH=amlens_seed_scratch

$PG psql -U amlens -d postgres -qc "DROP DATABASE IF EXISTS $SCRATCH" -c "CREATE DATABASE $SCRATCH"
export DATABASE_URL="postgresql+psycopg://amlens:amlens_dev@127.0.0.1:5433/$SCRATCH"
export PYTHONPATH="$ROOT"
(cd "$ROOT/backend" && "$PY" -m alembic upgrade head && "$PY" scripts/migrate_sqlite_to_postgres.py aml.db \
  && "$PY" -m alembic downgrade 0001_initial && "$PY" -m alembic upgrade head)   # re-run data backfills (alert statuses) on the copied rows
# Data only: the schema comes from the migrate job (alembic) in Azure.
$PG pg_dump -U amlens -d $SCRATCH --data-only --no-owner --no-privileges \
    --exclude-table=alembic_version > "$ROOT/infra/seed/seed.sql"
$PG psql -U amlens -d postgres -qc "DROP DATABASE $SCRATCH"
echo "Wrote infra/seed/seed.sql ($(wc -c < "$ROOT/infra/seed/seed.sql") bytes)"
