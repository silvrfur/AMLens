---
audience: developer
---

# Operations runbook

Procedures for operating the production AKS deployment. Commands are taken from the scripts in
`deploy/aks/`. Procedures that have no script behind them and have not been rehearsed are marked
**Untested**: read them through and try them on a non-production cluster first.

!!! danger "Production safety"
    - Run commands from the repository root in Git Bash (Windows), Linux or macOS.
    - Never commit `deploy/aks/.kubeconfig`, `deploy/aks/.credentials`, `.env` files or any key.
    - Never print secret values (`kubectl get secret -o yaml`, `describe secret`) into a shared
      terminal, chat or ticket.
    - Azure writes in the sandbox require MFA; if `az` fails with an authentication error, run
      `az login` again.

## Before you start

```bash
az login
az account set -s <subscription>
export RG=<resource-group>
export KUBECONFIG=deploy/aks/.kubeconfig      # written by deploy.sh
kubectl -n amlens get pods
```

If `deploy/aks/.kubeconfig` does not exist on your machine, create it without touching
`~/.kube/config`:

```bash
az aks get-credentials -g "$RG" -n aks-amlens --file deploy/aks/.kubeconfig
```

Names used below: namespace `amlens`; registry `<acr>` (= `acramlens<suffix>`); storage account
`<storage-account>` (= `stamlens<suffix>`); host `<host>` (=
`amlens-<suffix>.southindia.cloudapp.azure.com`). See
[resource naming](index.md#resource-naming).

## First deployment

1. Generate the sample data once (needs the local Docker PostgreSQL from
   `backend/docker-compose.yml` and the backend virtual environment):

    ```bash
    bash infra/seed/make-seed.sh
    ```

2. Make sure `TOKEN_SECRET` is available (team value, at least 32 characters) in
   `backend/.env` or `$AMLENS_TOKEN_SECRET`.
3. Deploy with the sample data:

    ```bash
    SEED=1 RG=<resource-group> bash deploy/aks/deploy.sh
    ```

    The first run takes about 10 minutes for the cluster plus image builds. It creates the first
    account (`analyst`, or `FIRST_USER=<name>`), whose password is appended to
    `deploy/aks/.credentials`.
4. Hand the password over privately, then delete `deploy/aks/.credentials`.
5. Verify: open `https://<host>`, sign in, open **Settings → Service health** (backend, agent and
   RAG healthy; queue "not applicable"), open an alert, run an investigation (about 30 s), check
   that the report cites guidance, record a decision, and confirm the audit trail shows your
   username as the analyst.

Full description of each step: [AKS deployment](aks-deployment.md).

## Release a new version

Normally a merge to `main` releases automatically ([CI/CD pipeline](ci-cd.md)). To release by
hand, from a clean checkout of the commit you want to ship:

```bash
git status --porcelain            # should print nothing
RG=<resource-group> TAG=$(git rev-parse --short HEAD) bash deploy/aks/rollout.sh
```

`rollout.sh` builds from `git archive HEAD`, so the images contain exactly the checked-out
commit. It runs the migrate Job, rolls out `rag`, `backend`, `frontend` in that order, and
smoke-tests `/api/backend/health`. Check afterwards:

```bash
kubectl -n amlens get deploy -o wide      # IMAGES column shows the new tag
curl -s https://<host>/api/backend/health
```

Re-run `deploy.sh` instead when you changed secrets, `edge.yaml`, `network-policy.yaml`,
`postgres.yaml`, `backup.yaml` or `signin-templates.yaml`: `rollout.sh` applies only
`jobs/migrate.yaml` and `base/apps.yaml`.

## Add or reset an analyst account

```bash
bash deploy/aks/add-user.sh <username>
```

- Usernames: 3–64 characters from `A-Z a-z 0-9 . _ @ -`.
- Generates a random 20-character password, stores only its bcrypt hash (cost 12) in the
  Secret `amlens-htpasswd`, and restarts `oauth2-proxy` so it reloads the file.
- Running it for an existing username **resets** that user's password.
- The plain password is appended to `deploy/aks/.credentials` (git-ignored). Hand it over through
  a private channel and delete the file afterwards.
- Needs Python with `bcrypt` (installed with `pip install --user bcrypt` if missing).

The username becomes the analyst name stored with decisions and audit events (see
[Authentication](../authentication/index.md)).

### Remove an account

**Untested** (no script exists). Rewrite the Secret without the user's line, then restart the
proxy:

```bash
USERS="$(kubectl -n amlens get secret amlens-htpasswd -o 'jsonpath={.data.users}' | base64 -d | grep -v '^<username>:')"
kubectl -n amlens create secret generic amlens-htpasswd --from-literal=users="$USERS" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n amlens rollout restart deploy/oauth2-proxy
```

The file contains only bcrypt hashes, but do not echo `$USERS`. Existing sessions stay valid
until their cookie expires (oauth2-proxy default: 7 days); rotate the cookie secret (see
[Rotate keys and secrets](#rotate-keys-and-secrets)) to sign everyone out immediately.

## Remove a demo dataset

`remove-dataset.sh` deletes one uploaded dataset and everything derived from it: transactions,
alerts, investigations, decisions, report versions, audit events and agent runs. Other datasets
are untouched. It also deletes that dataset's audit trail, so use it **only for demo or
rehearsal data**.

1. Dry run (default): runs the deletes in a transaction, prints counts, then rolls back.

    ```bash
    bash deploy/aks/remove-dataset.sh backend/examples/demo_wealth_book_nov2026.csv
    ```

    You can pass the CSV file that was uploaded (the dataset id is the first 20 hex characters of
    its SHA-256, the same id the upload uses) or the 20-character dataset id itself.

2. Check the printed counts (`transactions / alerts / investigations`), then apply:

    ```bash
    bash deploy/aks/remove-dataset.sh backend/examples/demo_wealth_book_nov2026.csv --apply
    ```

The script runs `psql` inside `postgres-0` with `kubectl exec`. After removal the same file can be
uploaded again.

## Backups

### Check the last backup

```bash
kubectl -n amlens get cronjob postgres-backup
kubectl -n amlens get jobs                     # postgres-backup-<n> jobs, last 3 kept
kubectl -n amlens logs job/<postgres-backup-job-name> -c upload
```

A successful run logs `uploaded amlens-<timestamp>.dump`.

### Trigger a backup now

```bash
kubectl -n amlens create job --from=cronjob/postgres-backup backup-now
kubectl -n amlens wait --for=condition=complete job/backup-now --timeout=300s
kubectl -n amlens logs job/backup-now -c upload
kubectl -n amlens delete job backup-now      # so the name can be reused
```

Take a manual backup before any risky operation (a restore, a destructive migration, removing a
dataset that is not pure demo data).

### List backups

The cluster's SAS cannot list or read; use your own Azure access:

```bash
ST_KEY="$(az storage account keys list -g "$RG" -n <storage-account> --query '[0].value' -o tsv)"
az storage blob list --account-name <storage-account> --account-key "$ST_KEY" \
  -c pg-backups --query "[].{name:name, size:properties.contentLength, modified:properties.lastModified}" -o table
```

Blobs older than 14 days are deleted by the lifecycle rule (if the rule could be created; check
with `az storage account management-policy show -g "$RG" --account-name <storage-account>`).

## Restore from a dump

**Untested.** There is no restore script; this procedure is derived from the backup format
(`pg_dump -Fc`, custom format) and the StatefulSet. Rehearse it on a non-production cluster.

1. **Take a fresh backup** of the current state ([Trigger a backup now](#trigger-a-backup-now)).
2. **Download** the dump you want:

    ```bash
    az storage blob download --account-name <storage-account> --account-key "$ST_KEY" \
      -c pg-backups -n amlens-<YYYYMMDDTHHMMSSZ>.dump -f amlens.dump
    ```

3. **Stop writers** so nothing changes the database during the restore:

    ```bash
    kubectl -n amlens scale deploy/backend --replicas=0
    ```

4. **Restore** into the running PostgreSQL. `--clean --if-exists` drops and re-creates the
   objects contained in the dump; custom-format dumps can be read from standard input:

    ```bash
    kubectl -n amlens exec -i postgres-0 -- \
      pg_restore -U amlens -d amlens --clean --if-exists --no-owner --single-transaction < amlens.dump
    ```

    `--single-transaction` makes the restore all-or-nothing. If it fails, the database is left as
    it was.
5. **Check the schema version** matches the code that will run against it:

    ```bash
    kubectl -n amlens exec postgres-0 -- psql -U amlens -d amlens -c 'SELECT version_num FROM alembic_version'
    ```

    If the dump is older than the current release, run the migrate Job (re-run `rollout.sh` for
    the current commit, or apply the rendered `deploy/aks/.build/migrate.yaml`).
6. **Start the backend** and verify:

    ```bash
    kubectl -n amlens scale deploy/backend --replicas=1
    kubectl -n amlens rollout status deploy/backend
    curl -s https://<host>/api/backend/health
    ```

To restore a lost **volume** (for example after deleting the PVC), redeploy with `deploy.sh`
(without `SEED=1`) to recreate an empty database and schema, then restore as above.

## Roll back a release

### Option 1: point the Deployments at the previous image

Images for every released tag stay in ACR. Find the previous tag and set it:

```bash
az acr repository show-tags -n <acr> --repository amlens-backend --orderby time_desc -o tsv | head
PREV=<previous-tag>
kubectl -n amlens set image deploy/rag      rag=<acr>.azurecr.io/amlens-rag:$PREV
kubectl -n amlens set image deploy/backend  backend=<acr>.azurecr.io/amlens-backend:$PREV
kubectl -n amlens set image deploy/frontend frontend=<acr>.azurecr.io/amlens-frontend:$PREV
kubectl -n amlens rollout status deploy/backend
```

Kubernetes also keeps earlier ReplicaSets, so `kubectl -n amlens rollout undo deploy/<name>`
returns a single Deployment to its previous revision.

This does **not** undo database migrations. That is fine as long as migrations were backward
compatible (the rule for this project). The next `rollout.sh` run overwrites the image again.

### Option 2: redeploy a previous commit

`rollout.sh` builds from the checked-out commit, so check that commit out first (a separate
worktree keeps your working copy intact):

```bash
git worktree add ../amlens-rollback <previous-sha>
cd ../amlens-rollback
RG=<resource-group> TAG=<previous-sha> bash deploy/aks/rollout.sh
```

Caution: the migrate Job of the older image runs `alembic upgrade head` with the older migration
set. If the database already has a newer revision that the older code does not know, Alembic
fails and the rollout stops before any application changes. In that case use option 1.

## View logs

```bash
kubectl -n amlens logs deploy/backend --since=1h           # backend + agents
kubectl -n amlens logs deploy/backend -f                   # follow
kubectl -n amlens logs deploy/backend --previous           # after a crash/restart
kubectl -n amlens logs deploy/rag --since=1h
kubectl -n amlens logs deploy/frontend --since=1h
kubectl -n amlens logs deploy/oauth2-proxy --since=1h      # sign-ins, auth requests
kubectl -n amlens logs job/migrate
kubectl -n app-routing-system logs deploy/amlens-nginx-0 --since=1h   # ingress access log
kubectl -n amlens get events --sort-by=.lastTimestamp | tail -30
```

Logs exist only as container stdout on the nodes; there is no central log store
(see [Monitoring](../monitoring/index.md)). The agents log structured JSON lines
(`tool_attempt`, run events) without prompt contents.

## Rotate keys and secrets

Rotate any key that has been shared outside the secret store (in chat, email, a screenshot or a
commit), and on a regular schedule. After changing a Secret, restart the pods that read it:
environment variables are read only at start-up.

| Secret | How to rotate | Restart |
|---|---|---|
| Azure OpenAI key (`amlens-ai/AZURE_OPENAI_API_KEY`) | `az cognitiveservices account keys regenerate -g "$RG" -n <openai-account> --key-name key1`, then re-run `deploy.sh` (it reads `key1` on every run) | `deploy/backend`, `deploy/rag` |
| AI Search query key (`amlens-ai/AZURE_SEARCH_ADMIN_KEY`) | `az search query-key create -g "$RG" --service-name <search-service> -n amlens-<date>`, delete the old one with `az search query-key delete -g "$RG" --service-name <search-service> --key-value <old-key>`, re-run `deploy.sh` (it takes the **first** query key, so remove the old key before re-running) | `deploy/rag` |
| AI Search admin keys (used only by the index scripts on a developer machine) | `az search admin-key renew -g "$RG" --service-name <search-service> --key-kind primary` | none in the cluster |
| Proxy key (`amlens-app/AML_PROXY_KEY`) | **Untested.** `deploy.sh` reuses the existing value, so replace it explicitly (below) | `deploy/backend` and `deploy/frontend` together |
| Cookie secret (`amlens-oauth/cookie-secret`) | **Untested.** Replace the key in `amlens-oauth` with a new random 32-byte URL-safe base64 value; signs every user out | `deploy/oauth2-proxy` |
| Entra client secret (`amlens-oauth/client-secret`) | Created valid for one year. Not used while password sign-in is active; renew with `az ad app credential reset` before enabling Entra ID | `deploy/oauth2-proxy` |
| Analyst passwords | `bash deploy/aks/add-user.sh <username>` | automatic |
| Backup SAS (`amlens-backup/BACKUP_SAS`) | Expires 365 days after the last `deploy.sh` run; re-run `deploy.sh` to issue a new one. To revoke a leaked SAS immediately, rotate the storage account key it was signed with (`az storage account keys renew`) and re-run `deploy.sh` | none (read per job) |
| Database password (`amlens-db`) | **Untested.** Change it in PostgreSQL (`ALTER USER amlens PASSWORD ...` through `kubectl exec postgres-0 -- psql`), then update all three keys of `amlens-db`. `POSTGRES_PASSWORD` in the StatefulSet is only used when the data directory is first created | `deploy/backend` |
| `TOKEN_SECRET` | **Do not rotate casually.** Account tokens in stored data are HMACs of this value; a new value means new uploads no longer match existing account tokens. Treat as a data migration | — |

Replacing the proxy key (**untested**), without printing the values:

```bash
NEW_KEY="$(python -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=').replace('-','').replace('_',''))")"
TOKEN_SECRET="$(kubectl -n amlens get secret amlens-app -o 'jsonpath={.data.TOKEN_SECRET}' | base64 -d)"
kubectl -n amlens create secret generic amlens-app \
  --from-literal=TOKEN_SECRET="$TOKEN_SECRET" --from-literal=AML_PROXY_KEY="$NEW_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n amlens rollout restart deploy/backend deploy/frontend
unset NEW_KEY TOKEN_SECRET
```

Requests fail with 401 for the few seconds in which one of the two pods still has the old key.

## Rebuild the AI Search index

Needed when the AI Search service or the index has been deleted or corrupted. The lab provider
has deleted the Search service once; it was recreated and the index rebuilt with this procedure.
Symptoms: investigations fail at the retrieval step and RAG logs show
`AML guidance search failed`, while `/api/backend/health` may still report RAG as healthy (the
RAG health probe does not call Azure).

1. **Recreate the service** in the same resource group and region if it is gone (portal, or
   `az search service create -g "$RG" -n <search-service> -l southindia --sku <sku>`). The SKU
   used before is not recorded in the repository; any SKU that supports vector search works.
2. **Configure `RAG/.env`** on your machine (git-ignored; template in `RAG/.env.example`):
   `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_ADMIN_KEY` (an **admin** key is required to create the
   index and upload documents; get it with
   `az search admin-key show -g "$RG" --service-name <search-service>`),
   `AZURE_SEARCH_INDEX_NAME=amlens-guidance-v1`, `AZURE_OPENAI_BASE_URL`
   (`https://<openai-account>.openai.azure.com/openai/v1/`), `AZURE_OPENAI_API_KEY`,
   `AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small`, `APPROVED_AML_DOCUMENTS`.
3. **Create the index** (1536-dimension `content_vector`, HNSW, cosine). If the index exists,
   the script only verifies its structure and never overwrites it:

    ```bash
    cd RAG
    python scripts/create_azure_search_index.py
    ```

4. **Upload all approved chunks**, dry run first. Embeddings are generated with
   `text-embedding-3-small` in batches of 8 and verified typology annotations from
   `app/typology_annotations.py` are attached:

    ```bash
    python scripts/upload_azure_chunks.py --limit 0            # dry run: lists what would be uploaded
    python scripts/upload_azure_chunks.py --limit 0 --upload
    ```

    The chunk source is the committed `RAG/indexes/aml_chunks_metadata.json`; no PDF processing
    is needed.
5. **Check the typology metadata** (optional; dry run by default, `--apply` merges corrections):

    ```bash
    python scripts/update_azure_typologies.py
    ```

6. **Verify retrieval**:

    ```bash
    python scripts/test_azure_retrieval.py
    ```

    To run the evaluation set against the deployed RAG service (**untested** against production),
    port-forward and point the evaluator at it:

    ```bash
    kubectl -n amlens port-forward deploy/rag 8001:8001 &
    RAG_EVAL_URL=http://127.0.0.1:8001/search python scripts/evaluate_azure_rag.py
    ```

7. **Update the cluster.** A recreated service has new keys (and possibly a new name): re-run
   `RG=<resource-group> bash deploy/aks/deploy.sh` from the repository root. It reads the
   Search service and its first query key from Azure, updates `amlens-ai` and `amlens-config`,
   and re-applies the workloads. Then restart RAG so it picks up the new values:

    ```bash
    kubectl -n amlens rollout restart deploy/rag
    ```

8. Run one investigation and confirm the report cites guidance.

## Troubleshooting

| Symptom | Likely cause | What to check / do |
|---|---|---|
| Pods stay `Pending` | Not enough CPU or memory requestable on the two B2s nodes (often after adding a replica, or when the add-on's default NGINX controller scaled back to 2 replicas) | `kubectl -n amlens describe pod <pod>` shows `Insufficient cpu` / `memory`. `kubectl top nodes`. Re-apply the patch from `deploy.sh`: `kubectl patch nginxingresscontroller default --type merge -p '{"spec":{"scaling":{"minReplicas":1,"maxReplicas":2,"threshold":"steady"}}}'`. Otherwise reduce requests or add a node (`NODES=3`, or `az aks scale`) |
| `502` with JSON `{"detail":"The backend service is unreachable."}` (or `rag`) | The frontend proxy could not connect to the upstream: backend/RAG pod not ready, crashing, or blocked by a network policy | `kubectl -n amlens get pods`, `logs deploy/backend --previous`, `get networkpolicy`. Check the pod labels still match the policies |
| `502`/`503` HTML page from NGINX | The frontend or oauth2-proxy pod is not ready, or the `/oauth2` rate limit (20 req/min per IP) was exceeded (`503`) | `kubectl -n amlens get pods`; ingress log `kubectl -n app-routing-system logs deploy/amlens-nginx-0` |
| `401 {"detail":"Not authenticated"}` from API calls | Backend and frontend disagree on the proxy key (one restarted after a key change, the other not) | `kubectl -n amlens rollout restart deploy/backend deploy/frontend` |
| Investigation fails; RAG returns `500 AML guidance search failed` | AI Search service or index missing, wrong key, or embedding deployment missing | `kubectl -n amlens logs deploy/rag`. If the Search service is gone: [Rebuild the AI Search index](#rebuild-the-ai-search-index). Health still shows RAG `healthy` because its probe does not call Azure |
| Investigation fails with an LLM error | Azure OpenAI key rotated without re-running `deploy.sh`, deployment `gpt-4.1-mini` missing, rate limit (429) or content filter | `kubectl -n amlens logs deploy/backend`. See [Azure OpenAI](../integrations/azure-openai.md#failure-handling) |
| Investigation stops after about 5 minutes | `proxy-read-timeout: 300` on the ingress; the investigation runs inside the HTTP request | Retry; check backend logs for the slow step |
| Sign-in page keeps coming back (loop) | Cookie not stored or not accepted: site opened over `http://` or another host name (`--cookie-secure`, `--whitelist-domain`), cookie secret changed, browser blocks cookies | Use `https://<host>` exactly; clear the site's cookies; `kubectl -n amlens logs deploy/oauth2-proxy` |
| "Invalid username or password" for a valid account | Account not in `amlens-htpasswd`, or proxy not restarted after `add-user.sh` | Re-run `add-user.sh <username>` (it restarts the proxy) |
| oauth2-proxy `CrashLoopBackOff` | Secret `amlens-htpasswd` or `amlens-oauth` missing | `kubectl -n amlens get secret`; re-run `deploy.sh` |
| Browser certificate warning | Let's Encrypt certificate not issued or not renewed | `kubectl -n amlens get certificate,certificaterequest,order,challenge`; `kubectl -n amlens describe challenge`. The HTTP-01 solver needs port 80 reachable and the `acme-solver-from-ingress` policy. Let's Encrypt rate limits apply to repeated re-issues |
| `migrate` Job fails | Migration error or database unreachable | `kubectl -n amlens logs job/migrate`; the old release is still serving |
| `Image build failed` from the scripts | ACR build error (logs are not streamed) | `az acr task list-runs -r <acr> -o table`, then `az acr task logs -r <acr> --run-id <id>` |
| Backup job failed | SAS expired (365 days), storage key rotated, or database unreachable | `kubectl -n amlens logs job/<name> -c dump` / `-c upload`; re-run `deploy.sh` to issue a new SAS |
| `az` asks for login during a script | Sandbox MFA policy | `az login`, then re-run the script; both scripts are safe to re-run |
