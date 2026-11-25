#!/bin/sh
# Loads /seed.sql into $DATABASE_URL once. The schema must already exist (migrate job).
set -eu
n=$(psql "$DATABASE_URL" -tAc 'SELECT count(*) FROM alerts')
if [ "$n" != "0" ]; then
  echo "alerts already has $n rows; not loading again"
  exit 0
fi
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction -q -f /seed.sql > /dev/null
echo "Loaded: $(psql "$DATABASE_URL" -tAc 'SELECT count(*) FROM alerts') alerts, $(psql "$DATABASE_URL" -tAc 'SELECT count(*) FROM transactions') transactions"
