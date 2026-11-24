#!/usr/bin/env bash
# Routine release to an existing AKS deployment (used by the GitHub Actions pipeline):
# build images -> migrate -> RAG -> backend -> frontend -> smoke test.
# Never touches infrastructure, secrets or the sign-in app (deploy.sh does that once).
#
#   RG=... TAG=<git sha> bash deploy/aks/rollout.sh
set -euo pipefail
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1   # Windows az CLI: avoid cp1252 crashes when streaming build logs
# On Windows the Azure CLI ends every output line with \r; strip it so values captured with
# $(az ...) (keys, IDs, URLs) are clean. pipefail keeps az's own exit status.
az() { command az "$@" | tr -d '\r'; }

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
RG="${RG:-tpl-azure-aks--mazeazusrqn9-ongz-sbx}"
LOC="${LOC:-southindia}"
SUF="$(printf %s "$RG" | md5sum | cut -c1-6)"
ACR="${ACR:-acramlens$SUF}"
AKS="${AKS:-aks-amlens}"
DNSLABEL="${DNSLABEL:-amlens-$SUF}"
HOST="$DNSLABEL.$LOC.cloudapp.azure.com"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
BUILD="$(mktemp -d)"

echo "== Build $TAG"
az acr build -r "$ACR" -t "amlens-rag:$TAG" RAG -o none
az acr build -r "$ACR" -t "amlens-backend:$TAG" -f backend/Dockerfile . -o none
az acr build -r "$ACR" -t "amlens-frontend:$TAG" frontend -o none

echo "== Cluster credentials"
az aks get-credentials -g "$RG" -n "$AKS" --overwrite-existing --file "$BUILD/kubeconfig" -o none
export KUBECONFIG="$BUILD/kubeconfig"
render() { sed -e "s#__ACR__#$ACR.azurecr.io#g" -e "s#__TAG__#$TAG#g" -e "s#__HOST__#$HOST#g" "$1" > "$BUILD/$(basename "$1")"; }
render deploy/aks/jobs/migrate.yaml; render deploy/aks/base/apps.yaml

echo "== Migrate"
kubectl -n amlens delete job migrate --ignore-not-found >/dev/null
kubectl apply -f "$BUILD/migrate.yaml" >/dev/null
kubectl -n amlens wait --for=condition=complete job/migrate --timeout=600s \
  || { kubectl -n amlens logs job/migrate --tail=50; exit 1; }

echo "== Roll out RAG, backend, frontend"
kubectl apply -n amlens -f "$BUILD/apps.yaml" >/dev/null
for d in rag backend frontend; do kubectl -n amlens rollout status "deploy/$d" --timeout=600s; done

echo "== Smoke test"
for i in $(seq 1 18); do
  H="$(curl -fsS "https://$HOST/api/backend/health" || true)"
  echo "$H" | grep -q '"backend":"healthy".*"agent":"healthy".*"rag":"healthy"' && { echo "$H"; exit 0; }
  sleep 10
done
echo "Unhealthy after rollout: $H"; exit 1
