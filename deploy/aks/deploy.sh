#!/usr/bin/env bash
# Deploys AMLens to AKS in one resource group (built for the training sandbox, where Container
# Apps and managed PostgreSQL are not allowed; see DEPLOY.md). Safe to re-run: existing secrets
# (database password, proxy key, sign-in app) are reused, not regenerated.
#
#   bash deploy/aks/deploy.sh            # from the repo root (Git Bash, Linux or macOS)
#   SEED=1 bash deploy/aks/deploy.sh     # also load the sample data into an empty database
#
# Needs: az (signed in), git, python. kubectl is installed by `az aks install-cli` if missing.
# Secrets come from local git-ignored files or the environment, never from arguments:
#   TOKEN_SECRET  $AMLENS_TOKEN_SECRET, else backend/.env  (must be the team's value)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
# The Windows Azure CLI crashes streaming `az acr build` logs on a cp1252 console.
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
# On Windows the Azure CLI ends every output line with \r; strip it so values captured with
# $(az ...) (keys, IDs, URLs) are clean. pipefail keeps az's own exit status.
az() { command az "$@" | tr -d '\r'; }
# Build in ACR without streaming logs (the Windows CLI crashes printing them); still waits.
acr_build() {
  local status; status="$(az acr build -r "$ACR" "$@" --no-logs --query status -o tsv 2>/dev/null || true)"
  [ "$status" = Succeeded ] || { echo "Image build failed (${status:-error}): $*  -> az acr task list-runs -r $ACR"; exit 1; }
  echo "  built: $2"
}
# Build contexts are clean exports of the committed code (git archive): no node_modules,
# .venv or git-ignored files such as .env, and no Windows path-length failures.
ctx() { local d="$CTX/$1"; shift; rm -rf "$d"; mkdir -p "$d"; git archive --format=tar HEAD "$@" | tar -x -C "$d"; printf %s "$d"; }
RG="${RG:-tpl-azure-aks--mazeazusrqn9-ongz-sbx}"
LOC="${LOC:-southindia}"
SUF="$(printf %s "$RG" | md5sum | cut -c1-6)"
ACR="${ACR:-acramlens$SUF}"
AKS="${AKS:-aks-amlens}"
ST="${ST:-stamlens$SUF}"
DNSLABEL="${DNSLABEL:-amlens-$SUF}"
HOST="$DNSLABEL.$LOC.cloudapp.azure.com"
NODE_SIZE="${NODE_SIZE:-Standard_B2s}"
NODES="${NODES:-2}"
CERT_MANAGER_VERSION="v1.16.2"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
[ -z "$(git status --porcelain --untracked-files=no)" ] || TAG="$TAG-dirty$(date +%m%d%H%M)"
export KUBECONFIG="$ROOT/deploy/aks/.kubeconfig"      # never touches ~/.kube/config
KUBECTL_DIR="$HOME/.azure-kubectl"; export PATH="$KUBECTL_DIR:$PATH"
BUILD="$ROOT/deploy/aks/.build"; rm -rf "$BUILD"; mkdir -p "$BUILD"
say() { printf '\n== %s\n' "$*"; }
rand() { python -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes($1)).decode())"; }
secret_value() { kubectl -n amlens get secret "$1" -o "jsonpath={.data.$2}" 2>/dev/null | base64 -d 2>/dev/null || true; }
dotenv() { [ -f "$1" ] && sed -n "s/^[[:space:]]*$2[[:space:]]*=[[:space:]]*//p" "$1" | tail -1 | tr -d '\r' || true; }

# ------------------------------------------------------------------ preflight
say "Preflight"
az account show --query "{subscription:name, user:user.name}" -o tsv
TOKEN_SECRET="${AMLENS_TOKEN_SECRET:-$(dotenv backend/.env TOKEN_SECRET)}"
[ "${#TOKEN_SECRET}" -ge 32 ] || { echo "TOKEN_SECRET (team value, >=32 chars) not found"; exit 1; }
[ "${SEED:-0}" != 1 ] || [ -f infra/seed/seed.sql ] || { echo "Run: bash infra/seed/make-seed.sh"; exit 1; }
TENANT="$(az account show --query tenantId -o tsv)"
CHAT_DEPLOYMENT="${CHAT_DEPLOYMENT:-gpt-4.1-mini}"
# The Azure OpenAI / AI Services account that actually hosts the chat deployment.
OPENAI="${OPENAI:-}"
if [ -z "$OPENAI" ]; then
  for a in $(az cognitiveservices account list -g "$RG" --query "[?kind=='AIServices' || kind=='OpenAI'].name" -o tsv | tr -d '\r'); do
    az cognitiveservices account deployment show -g "$RG" -n "$a" --deployment-name "$CHAT_DEPLOYMENT" -o none 2>/dev/null && { OPENAI="$a"; break; }
  done
fi
[ -n "$OPENAI" ] || { echo "No Azure OpenAI account in $RG has a '$CHAT_DEPLOYMENT' deployment"; exit 1; }
OPENAI_ENDPOINT="https://$OPENAI.openai.azure.com/"
SEARCH="$(az search service list -g "$RG" --query "[0].name" -o tsv)"
echo "image tag $TAG | host https://$HOST | openai $OPENAI | search $SEARCH"

# ------------------------------------------------------------------ 1. platform
say "1/7 Platform: registry, storage, AKS (first run ~10 min)"
az acr show -n "$ACR" -o none 2>/dev/null || az acr create -g "$RG" -n "$ACR" -l "$LOC" --sku Basic --admin-enabled false -o none
if ! az storage account show -g "$RG" -n "$ST" -o none 2>/dev/null; then
  az storage account create -g "$RG" -n "$ST" -l "$LOC" --sku Standard_LRS --kind StorageV2 \
    --min-tls-version TLS1_2 --allow-blob-public-access false -o none
fi
ST_KEY="$(az storage account keys list -g "$RG" -n "$ST" --query "[0].value" -o tsv)"
az storage container create --account-name "$ST" --account-key "$ST_KEY" -n pg-backups -o none
az storage account management-policy create -g "$RG" --account-name "$ST" -o none --policy '{"rules":[{"enabled":true,"name":"expire-backups","type":"Lifecycle","definition":{"actions":{"baseBlob":{"delete":{"daysAfterModificationGreaterThan":14}}},"filters":{"blobTypes":["blockBlob"],"prefixMatch":["pg-backups/"]}}}]}' \
  || echo "  (lifecycle rule not allowed here; prune old backups manually)"
if ! az aks show -g "$RG" -n "$AKS" -o none 2>/dev/null; then
  az aks create -g "$RG" -n "$AKS" -l "$LOC" --tier free \
    --node-count "$NODES" --node-vm-size "$NODE_SIZE" --os-sku Ubuntu \
    --network-plugin azure --network-plugin-mode overlay --network-dataplane cilium \
    --enable-managed-identity --enable-oidc-issuer --enable-workload-identity \
    --enable-app-routing --attach-acr "$ACR" --generate-ssh-keys -o none
fi
az aks get-credentials -g "$RG" -n "$AKS" --overwrite-existing -o none
command -v kubectl >/dev/null || az aks install-cli --install-location "$KUBECTL_DIR/kubectl$( [ "${OS:-}" = Windows_NT ] && echo .exe )" -o none
kubectl get nodes -o wide

# ------------------------------------------------------------------ 2. images
say "2/7 Images (built in ACR)"
CTX="$(mktemp -d)"
acr_build -t "amlens-rag:$TAG" "$(ctx rag RAG)/RAG"
acr_build -t "amlens-backend:$TAG" -f backend/Dockerfile "$(ctx backend backend agents .dockerignore)"
acr_build -t "amlens-frontend:$TAG" "$(ctx frontend frontend)/frontend"
if [ "${SEED:-0}" = 1 ]; then   # seed.sql is generated locally and git-ignored
  SEED_CTX="$(ctx seed infra/seed)/infra/seed"; cp infra/seed/seed.sql "$SEED_CTX/"
  acr_build -t "amlens-seed:$TAG" "$SEED_CTX"
fi
for img in "docker.io/library/postgres:16-alpine library/postgres:16-alpine" \
           "quay.io/oauth2-proxy/oauth2-proxy:v7.7.1 oauth2-proxy/oauth2-proxy:v7.7.1" \
           "docker.io/curlimages/curl:8.11.0 curlimages/curl:8.11.0"; do
  set -- $img
  az acr repository show -n "$ACR" --image "$2" -o none 2>/dev/null || az acr import -n "$ACR" --source "$1" --image "$2" -o none
done

# ------------------------------------------------------------------ 3. cluster add-ons
say "3/7 cert-manager"
kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/$CERT_MANAGER_VERSION/cert-manager.yaml" >/dev/null
kubectl -n cert-manager wait --for=condition=Available deploy --all --timeout=300s
# The app-routing add-on's default NGINX controller is unused (AMLens has its own, with the
# DNS label); keep it at one replica so it doesn't reserve a full vCPU on the small nodes.
kubectl patch nginxingresscontroller default --type merge \
  -p '{"spec":{"scaling":{"minReplicas":1,"maxReplicas":2,"threshold":"steady"}}}' >/dev/null

# ------------------------------------------------------------------ 4. sign-in (Entra ID app)
say "4/7 Entra ID sign-in app"
kubectl create namespace amlens --dry-run=client -o yaml | kubectl apply -f - >/dev/null
CLIENT_ID="$(secret_value amlens-oauth client-id)"
if [ -z "$CLIENT_ID" ]; then
  CLIENT_ID="$(az ad app create --display-name "AMLens ($RG)" --sign-in-audience AzureADMyOrg \
      --web-redirect-uris "https://$HOST/oauth2/callback" --query appId -o tsv)"
  CLIENT_SECRET="$(az ad app credential reset --id "$CLIENT_ID" --display-name oauth2-proxy --years 1 --query password -o tsv)"
  SP_ID="$(az ad sp create --id "$CLIENT_ID" --query id -o tsv)"
  # Only users assigned to the app may sign in; assign the person deploying.
  az ad sp update --id "$SP_ID" --set appRoleAssignmentRequired=true
  ME="$(az ad signed-in-user show --query id -o tsv)"
  az rest --method POST --url "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_ID/appRoleAssignedTo" \
    --body "{\"principalId\":\"$ME\",\"resourceId\":\"$SP_ID\",\"appRoleId\":\"00000000-0000-0000-0000-000000000000\"}" -o none
  kubectl -n amlens create secret generic amlens-oauth --from-literal=client-id="$CLIENT_ID" \
    --from-literal=client-secret="$CLIENT_SECRET" --from-literal=cookie-secret="$(rand 32)" >/dev/null
fi
echo "  app registration: $CLIENT_ID"

# ------------------------------------------------------------------ 5. config and secrets
say "5/7 Config and secrets"
apply_secret() { local name="$1"; shift; kubectl -n amlens create secret generic "$name" "$@" --dry-run=client -o yaml | kubectl apply -f - >/dev/null; }
PG_PASSWORD="$(secret_value amlens-db POSTGRES_PASSWORD)"; [ -n "$PG_PASSWORD" ] || PG_PASSWORD="$(rand 24 | tr -d '=_-')"
PROXY_KEY="$(secret_value amlens-app AML_PROXY_KEY)"; [ -n "$PROXY_KEY" ] || PROXY_KEY="$(rand 32 | tr -d '=_-')"
DB_URL="postgresql://amlens:$PG_PASSWORD@postgres:5432/amlens"
apply_secret amlens-db --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD" --from-literal=DATABASE_URL="$DB_URL" --from-literal=DATABASE_URL_LIBPQ="$DB_URL"
apply_secret amlens-app --from-literal=TOKEN_SECRET="$TOKEN_SECRET" --from-literal=AML_PROXY_KEY="$PROXY_KEY"
# Azure OpenAI / AI Search keys (read from Azure each run, so a key rotation is picked up).
apply_secret amlens-ai \
  --from-literal=AZURE_OPENAI_API_KEY="$(az cognitiveservices account keys list -g "$RG" -n "$OPENAI" --query key1 -o tsv)" \
  --from-literal=AZURE_SEARCH_ADMIN_KEY="$(az search query-key list -g "$RG" --service-name "$SEARCH" --query "[0].key" -o tsv)"
SAS_EXPIRY="$(python -c "import datetime;print((datetime.datetime.utcnow()+datetime.timedelta(days=365)).strftime('%Y-%m-%dT%H:%MZ'))")"
apply_secret amlens-backup \
  --from-literal=BACKUP_CONTAINER_URL="https://$ST.blob.core.windows.net/pg-backups" \
  --from-literal=BACKUP_SAS="$(az storage container generate-sas --account-name "$ST" --account-key "$ST_KEY" -n pg-backups --permissions cw --expiry "$SAS_EXPIRY" --https-only -o tsv)"
kubectl -n amlens create configmap amlens-config --dry-run=client -o yaml \
  --from-literal=AZURE_OPENAI_ENDPOINT="$OPENAI_ENDPOINT" \
  --from-literal=AZURE_OPENAI_DEPLOYMENT="${CHAT_DEPLOYMENT:-gpt-4.1-mini}" \
  --from-literal=AZURE_OPENAI_BASE_URL="${OPENAI_ENDPOINT}openai/v1/" \
  --from-literal=AZURE_OPENAI_EMBEDDING_DEPLOYMENT="${EMBEDDING_DEPLOYMENT:-text-embedding-3-small}" \
  --from-literal=AZURE_SEARCH_ENDPOINT="https://$SEARCH.search.windows.net" \
  --from-literal=AZURE_SEARCH_INDEX_NAME="${SEARCH_INDEX:-amlens-guidance-v1}" | kubectl apply -f - >/dev/null

# ------------------------------------------------------------------ 6. workloads
say "6/7 Workloads"
render() { sed -e "s#__ACR__#$ACR.azurecr.io#g" -e "s#__TAG__#$TAG#g" -e "s#__HOST__#$HOST#g" \
               -e "s#__DNSLABEL__#$DNSLABEL#g" -e "s#__TENANT__#$TENANT#g" "$1" > "$BUILD/$(basename "$1")"; }
for f in deploy/aks/base/*.yaml deploy/aks/jobs/*.yaml; do render "$f"; done
kubectl apply -n amlens -f "$BUILD/postgres.yaml" -f "$BUILD/network-policy.yaml" -f "$BUILD/backup.yaml" >/dev/null
kubectl -n amlens rollout status statefulset/postgres --timeout=300s
run_job() {
  kubectl -n amlens delete job "$1" --ignore-not-found >/dev/null
  kubectl apply -f "$BUILD/$1.yaml" >/dev/null
  if ! kubectl -n amlens wait --for=condition=complete "job/$1" --timeout=600s; then
    kubectl -n amlens logs "job/$1" --tail=50 || true; echo "Job $1 failed"; exit 1
  fi
  kubectl -n amlens logs "job/$1" --tail=5
}
run_job migrate
[ "${SEED:-0}" != 1 ] || run_job seed
# Order: RAG, then backend, then frontend.
kubectl apply -n amlens -f "$BUILD/apps.yaml" >/dev/null
for d in rag backend frontend; do kubectl -n amlens rollout status "deploy/$d" --timeout=600s; done
# Sign-in: username/password accounts (the lab tenant needs an admin to approve Entra ID apps).
kubectl -n amlens get secret amlens-htpasswd >/dev/null 2>&1 || bash deploy/aks/add-user.sh "${FIRST_USER:-analyst}"
kubectl apply -f "$BUILD/signin-templates.yaml" >/dev/null
kubectl apply -f "$BUILD/edge.yaml" >/dev/null
kubectl -n amlens rollout status deploy/oauth2-proxy --timeout=300s

# ------------------------------------------------------------------ 7. check
say "7/7 HTTPS certificate and health"
kubectl -n amlens wait --for=condition=Ready certificate/amlens-tls --timeout=600s
for i in $(seq 1 30); do
  H="$(curl -fsS "https://$HOST/api/backend/health" || true)"
  echo "$H" | grep -q '"backend":"healthy".*"rag":"healthy"' && break; sleep 10
done
echo "  health: $H"
echo "$H" | grep -q '"rag":"healthy"' || { echo "Not healthy yet: kubectl -n amlens get pods"; exit 1; }
printf '\nDone: https://%s  (accounts: bash deploy/aks/add-user.sh <name>; passwords in deploy/aks/.credentials)\n' "$HOST"
