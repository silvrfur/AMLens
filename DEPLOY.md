# Deploying AMLens to Azure

> **Live deployment (training sandbox): AKS.** The sandbox subscription allows only AKS, VMs,
> ACR, Storage and Key Vault in one resource group in `southindia` (no Container Apps, no managed
> PostgreSQL, no private DNS), so AMLens runs on AKS there: `deploy/aks/`.
> The Container Apps design further below (`infra/`) is for an unrestricted subscription.

## AKS (current deployment)

| Piece | How |
|---|---|
| URL | `https://amlens-<suffix>.southindia.cloudapp.azure.com` (Azure DNS label on the ingress load balancer) |
| Cluster | AKS, 2 × Standard_B2s, Azure CNI overlay + Cilium (network policies enforced) |
| Edge | App-routing NGINX, Let's Encrypt (cert-manager), sign-in via oauth2-proxy with **username/password** accounts (bcrypt, rate-limited); `/api/backend/health` is the only public path. Entra ID is configured too, but the lab tenant needs an admin to approve the app; once approved, remove the three htpasswd/template flags in `edge.yaml` |
| Apps | `rag`, `backend` (+ agents), `frontend` Deployments; backend and RAG reachable only from inside the namespace |
| Database | PostgreSQL 16 StatefulSet on an Azure managed disk; nightly `pg_dump` CronJob to Blob Storage (write-only SAS, 14-day lifecycle) |
| Secrets | Kubernetes Secrets created by `deploy.sh` (never in git): DB password, proxy key, `TOKEN_SECRET`, Azure OpenAI key, Search **query** (read-only) key, backup SAS |

```bash
bash infra/seed/make-seed.sh               # once, needs the local docker database
SEED=1 bash deploy/aks/deploy.sh           # first deploy (Git Bash / Linux / macOS, az signed in)
RG=<rg> TAG=<sha> bash deploy/aks/rollout.sh   # routine release (what CI runs)
```

Analyst accounts: `bash deploy/aks/add-user.sh <username>` creates or resets one; the password goes to the
git-ignored `deploy/aks/.credentials`. Hand it over privately, then delete the file.

Operate with `export KUBECONFIG=deploy/aks/.kubeconfig` (written by deploy.sh):
`kubectl -n amlens get pods`, `kubectl -n amlens logs deploy/backend`,
backups: `kubectl -n amlens create job --from=cronjob/postgres-backup backup-now`.

Sandbox limits to know: Azure writes need MFA (`az login` again when prompted); the lab
subscription may expire; Azure OpenAI/Search use keys (workload identity is not allowed here).

---

Target: **Azure Container Apps** in a VNet, defined in `infra/main.bicep` and rolled out by
`infra/deploy.ps1` (first time) and `.github/workflows/ci-cd.yml` (every merge to `main`).

```
 browser ──HTTPS──▶ frontend (public, Entra ID sign-in)
                       │  /api/backend/*  + X-AMLens-Proxy-Key, X-AMLens-User
                       ├────────────────▶ backend + agents (internal) ──▶ PostgreSQL Flexible Server
                       │                        │                         private access only, 14-day PITR
                       │                        ├──▶ Azure OpenAI (managed identity)
                       │  /api/rag/*            ▼
                       └────────────────▶ RAG (internal) ──▶ Azure AI Search + embeddings (managed identity)
```

| What | How |
|---|---|
| Network | VNet `10.40.0.0/16`: apps subnet, PostgreSQL subnet (delegated, private DNS). PostgreSQL has **no public endpoint**. |
| Ingress | Only the frontend is public. Backend and RAG are internal; the backend also requires the proxy's shared key. |
| Sign-in | Container Apps authentication (Entra ID) on the frontend. Only `/api/backend/health` (status only) is open. |
| Secrets | Key Vault (RBAC). Apps read them with their own user-assigned managed identities. No keys in app settings. |
| Azure OpenAI / AI Search | Managed identity (`Cognitive Services OpenAI User`, `Search Index Data Reader`). Keys mode is a fallback. |
| Images | Azure Container Registry, pulled with managed identities (admin user disabled). |
| Database | `alembic upgrade head` and the one-off data load run as Container Apps **jobs inside the VNet**. |
| Agent runs | PostgreSQL schema `agent_runtime`, so backend replicas and restarts are safe. |
| Backups | Automatic, 14-day point-in-time restore (`postgresBackupRetentionDays`, up to 35; geo-redundant optional). |
| Logs | Log Analytics workspace (30 days). |

Rough cost at idle: PostgreSQL B1ms ≈ US$15/month, Container Apps 3 × 1 always-on replica (consumption) ≈ US$30–50,
ACR Basic ≈ US$5, Key Vault/Log Analytics a few dollars. Delete the resource group to stop all charges.

## 1. One-time prerequisites (need someone with access)

1. **Azure sign-in:** `az login` (and `az account set -s <subscription>`). You need Owner, or
   Contributor + User Access Administrator, on the subscription or resource group (the template creates role assignments).
2. **Rotate the keys** that were shared in chat (Azure OpenAI, AI Search) before going live.
3. **Entra ID app registration** for sign-in:
   ```powershell
   $app = az ad app create --display-name "AMLens" --sign-in-audience AzureADMyOrg --identifier-uris "api://placeholder" | ConvertFrom-Json
   az ad app update --id $app.appId --identifier-uris "api://$($app.appId)"
   $env:AMLENS_AUTH_CLIENT_SECRET = (az ad app credential reset --id $app.appId --query password -o tsv)
   ```
   After the first deploy, add the redirect URI `https://<frontend fqdn>/.auth/login/aad/callback`
   (`az ad app update --id <appId> --web-redirect-uris ...`). Restrict who can sign in with
   *Enterprise applications → AMLens → Assignment required = Yes* and assign the analysts.
4. **AI Search RBAC:** Search service → Settings → Keys → API access control: *Both* (or *Role-based*).
5. **Data seed** (sample data from `backend/aml.db`): `bash infra/seed/make-seed.sh` (needs the local docker database).

## 2. Deploy

```powershell
.\infra\deploy.ps1 `
  -ResourceGroup rg-amlens -Location <region of the AI resources> `
  -AzureOpenAIEndpoint https://<openai>.openai.azure.com/ `
  -AzureSearchEndpoint https://<search>.search.windows.net `
  -AzureOpenAIResourceId (az cognitiveservices account show -n <openai> -g <rg> --query id -o tsv) `
  -AzureSearchResourceId (az search service show -n <search> -g <rg> --query id -o tsv) `
  -AuthClientId <appId> -Seed
```

It reads `TOKEN_SECRET` from `backend\.env` (or `$env:AMLENS_TOKEN_SECRET`): it must be the team's
existing value, or account tokens in the loaded data won't match new uploads. It generates the
PostgreSQL password and proxy key once and stores them in Key Vault; re-runs reuse them.

Steps it performs: platform → build images in ACR → RAG, backend, frontend, jobs → migrate job →
seed job → backend restart → health check through the public URL.

If the AI resources are in a subscription where you can't create role assignments, use
`-AIAuth keys` (keys read from `backend\.env` / `RAG\.env` into Key Vault).

## 3. Verify

1. Open the printed URL and sign in.
2. Settings → Service health: backend, agent and RAG healthy; queue "not applicable".
3. Open an alert, run an investigation (≈30 s), check the report cites guidance, record a decision,
   and confirm the audit trail shows **your signed-in name** as the analyst.

## 4. CI/CD (GitHub Actions)

`.github/workflows/ci-cd.yml`: every PR and push runs agent tests (SQLite + PostgreSQL), backend tests,
a RAG import check without torch, and the frontend type-check/build. Pushes to `main` then build the
images in ACR (tag = commit SHA), run migrations, roll out RAG → backend → frontend, and smoke-test health.

One-time setup (OIDC, no stored passwords):

```powershell
$repo = "silvrfur/AMLens"
$ci = az ad app create --display-name "AMLens GitHub deploy" | ConvertFrom-Json
az ad sp create --id $ci.appId | Out-Null
az ad app federated-credential create --id $ci.appId --parameters "{\"name\":\"github-production\",\"issuer\":\"https://token.actions.githubusercontent.com\",\"subject\":\"repo:${repo}:environment:production\",\"audiences\":[\"api://AzureADTokenExchange\"]}"
az role assignment create --assignee $ci.appId --role Contributor --scope (az group show -n rg-amlens --query id -o tsv)
```

Then in GitHub → Settings: create environment **production** (add required reviewers to gate releases),
and repository **variables** `AZURE_CLIENT_ID` (= `$ci.appId`), `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`AZURE_RESOURCE_GROUP` (`rg-amlens`), `AZURE_ACR_NAME` (printed by deploy.ps1 / `az acr list -g rg-amlens`).

Migrations run before the new backend starts, so they must stay backward compatible with the
previous release (add columns/tables first, remove them in a later release).

## 5. Operations

- **Logs:** Log Analytics → `ContainerAppConsoleLogs_CL`, or `az containerapp logs show -n amlens-backend -g rg-amlens --follow`.
- **Database access** (private): run a job or `az containerapp exec -n amlens-backend -g rg-amlens` — there is no public endpoint.
- **Restore:** `az postgres flexible-server restore --source-server <pg> --restore-time <UTC> -n <new>` (then point `database-url` at it).
- **Rollback:** `az containerapp update -n amlens-<app> -g rg-amlens --image <acr>.azurecr.io/amlens-<app>:<previous sha>`.
- **Clean up:** `az group delete -n rg-amlens`. Key Vault has purge protection: the vault name stays reserved for 30 days.

## Remaining gaps before real customer data

- PostgreSQL still uses a password (stored in Key Vault). Entra ID authentication for PostgreSQL
  needs token refresh in the backend's connection code.
- Key Vault, ACR, Azure OpenAI and AI Search are reached over their public endpoints (RBAC-protected).
  Private endpoints need ACR Premium and DNS zones per service.
- No rate limiting or WAF in front of the frontend (Front Door / Application Gateway).
- Investigations run inside the HTTP request. A Service Bus queue (the agents contain a worker) would
  make long or bulk runs survive restarts.
