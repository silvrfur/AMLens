#!/usr/bin/env bash
# Removes ONE uploaded dataset and everything created from it (alerts, investigations,
# decisions, report versions, audit events, agent runs) from the live AKS database, so a demo
# file can be uploaded again. Other datasets are untouched.
#
#   bash deploy/aks/remove-dataset.sh backend/examples/demo_wealth_book_nov2026.csv   # dry run
#   bash deploy/aks/remove-dataset.sh backend/examples/demo_wealth_book_nov2026.csv --apply
#   bash deploy/aks/remove-dataset.sh <20-char dataset id> [--apply]
#
# Dry run (default) executes the deletes in a transaction, prints the counts and rolls back.
# This also deletes the dataset's audit trail: use it for demo/rehearsal data only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export KUBECONFIG="${KUBECONFIG:-$ROOT/deploy/aks/.kubeconfig}"
ARG="${1:?usage: remove-dataset.sh <csv file | dataset id> [--apply]}"
if [ -f "$ARG" ]; then ID="$(sha256sum "$ARG" | cut -c1-20)"; else ID="$ARG"; fi   # same id the upload uses
[[ "$ID" =~ ^[0-9a-f]{20}$ ]] || { echo "Not a dataset id: $ID"; exit 1; }
END=ROLLBACK; [ "${2:-}" = "--apply" ] && END=COMMIT

echo "Dataset $ID ($([ "$END" = COMMIT ] && echo 'DELETING' || echo 'dry run, nothing is changed'))"
kubectl -n amlens exec -i postgres-0 -- psql -U amlens -d amlens -v ON_ERROR_STOP=1 -q -v id="$ID" <<SQL
BEGIN;
CREATE TEMP TABLE d_alerts ON COMMIT DROP AS
  SELECT a.id FROM alerts a JOIN transactions t ON t.id = a.transaction_id WHERE t.dataset_id = :'id';
CREATE TEMP TABLE d_inv ON COMMIT DROP AS
  SELECT id FROM investigations WHERE alert_id IN (SELECT id FROM d_alerts);
\echo transactions / alerts / investigations in this dataset:
SELECT (SELECT count(*) FROM transactions WHERE dataset_id = :'id') AS transactions,
       (SELECT count(*) FROM d_alerts) AS alerts, (SELECT count(*) FROM d_inv) AS investigations;
DELETE FROM agent_runtime.tool_calls WHERE run_id IN
  (SELECT run_id FROM agent_runtime.agent_runs WHERE investigation_id IN (SELECT id FROM d_inv));
DELETE FROM agent_runtime.agent_runs   WHERE investigation_id IN (SELECT id FROM d_inv);
DELETE FROM agent_runtime.audit_log    WHERE investigation_id IN (SELECT id FROM d_inv);
DELETE FROM agent_runtime.investigations WHERE investigation_id IN (SELECT id FROM d_inv);
DELETE FROM audit_history          WHERE investigation_id IN (SELECT id FROM d_inv);
DELETE FROM report_versions        WHERE investigation_id IN (SELECT id FROM d_inv);
DELETE FROM investigator_decisions WHERE investigation_id IN (SELECT id FROM d_inv);
DELETE FROM investigations WHERE id IN (SELECT id FROM d_inv);
DELETE FROM alerts         WHERE id IN (SELECT id FROM d_alerts);
DELETE FROM transactions   WHERE dataset_id = :'id';
\echo remaining rows for this dataset after the deletes:
SELECT count(*) AS transactions_left FROM transactions WHERE dataset_id = :'id';
$END;
SQL
echo "Done ($END)."
