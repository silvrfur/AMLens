#!/usr/bin/env bash
# Adds (or resets) an AMLens analyst account for the sign-in proxy and prints its password once.
#   bash deploy/aks/add-user.sh <username>
# Accounts are bcrypt hashes in the Kubernetes secret amlens-htpasswd; plain passwords are
# never stored. The new password is also appended to deploy/aks/.credentials (git-ignored)
# so it is not lost; hand it over privately and delete that file afterwards.
set -euo pipefail
USER_NAME="${1:?usage: add-user.sh <username>}"
[[ "$USER_NAME" =~ ^[A-Za-z0-9._@-]{3,64}$ ]] || { echo "Username: 3-64 of A-Z a-z 0-9 . _ @ -"; exit 1; }
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export KUBECONFIG="${KUBECONFIG:-$ROOT/deploy/aks/.kubeconfig}"
python -c "import bcrypt" 2>/dev/null || python -m pip install -q --user bcrypt >/dev/null

PASSWORD="$(python -c "import secrets,string;a=string.ascii_letters+string.digits;print(''.join(secrets.choice(a) for _ in range(20)))")"
HASH="$(PW="$PASSWORD" python -c "import bcrypt,os;print(bcrypt.hashpw(os.environ['PW'].encode(),bcrypt.gensalt(12)).decode().replace('\$2b\$','\$2y\$',1))")"

EXISTING="$(kubectl -n amlens get secret amlens-htpasswd -o 'jsonpath={.data.users}' 2>/dev/null | base64 -d 2>/dev/null || true)"
USERS="$(printf '%s\n' "$EXISTING" | grep -v "^$USER_NAME:" | grep -v '^$' || true)"
USERS="$(printf '%s\n%s:%s\n' "$USERS" "$USER_NAME" "$HASH" | grep -v '^$')"
kubectl -n amlens create secret generic amlens-htpasswd --from-literal=users="$USERS" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
# oauth2-proxy reads the file at start-up; restart it if it is already running.
kubectl -n amlens get deploy oauth2-proxy >/dev/null 2>&1 && kubectl -n amlens rollout restart deploy/oauth2-proxy >/dev/null || true

printf '%s  %s  %s\n' "$(date -u +%FT%TZ)" "$USER_NAME" "$PASSWORD" >> "$ROOT/deploy/aks/.credentials"
echo "Account '$USER_NAME' ready. Password saved to deploy/aks/.credentials (git-ignored)."
