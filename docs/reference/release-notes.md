---
audience: reference
---

# Release notes

AMLens has no numbered releases yet. These notes group the history of the `main` branch
(`git log --oneline main`) by theme, with commit dates. On `main` itself there are only two
first-parent commits: the initial commit (2026-11-19) and the merge of pull request #2
(2026-11-25), which brought in the integration of the member branches and all deployment work.

The production deployment on AKS was running image tag `f204b1a` on 2026-11-25 (verified live),
which is the last commit before the pull request #2 merge.

## 2026-11-25: Pull request #2 merged (`dc683f9`)

Merge of `deploy/azure-container-apps` into `main`. Everything in the sections below dated
2026-11-20 to 2026-11-25 reached `main` through this merge.

### Operations and analyst workflow

- `f204b1a` (2026-11-25) Let a failed investigation be opened and run again from its page.
  See [Retrying a failed investigation](../user-guide/workflows/retry-failed-investigation.md).
- `23a21c5` (2026-11-25) Add `deploy/aks/remove-dataset.sh` to remove one uploaded dataset and
  everything derived from it from the live database (dry run by default, `--apply` to commit).
  See the [runbook](../developer-guide/deployment/operations-runbook.md#remove-a-demo-dataset).

## 2026-11-24: Deployment to Azure

### AKS deployment (production)

- `5ed2b34` Add the AKS deployment for the sandbox subscription: `deploy/aks/deploy.sh`,
  manifests for the apps, in-cluster PostgreSQL 16, network policies, nightly backups to Blob
  Storage, NGINX ingress with Let's Encrypt and oauth2-proxy.
- `818fe76` Make the AKS scripts work from Windows (Git Bash) and deploy from CI: add
  `deploy/aks/rollout.sh` and switch the GitHub Actions deploy job to it.
- `9f22bd4` Build images with `--no-logs` so the Windows Azure CLI does not crash while
  streaming build logs.
- `8fb12a0` Build images from `git archive` exports of the committed code (no `node_modules`,
  virtual environments or `.env` files in build contexts).
- `eb9d35d` Run each ingress controller with one replica so everything fits on the two small
  sandbox nodes.
- `47a4548` Document the AKS deployment used in the sandbox subscription (`DEPLOY.md`).
- `5d02172` Use username/password sign-in (oauth2-proxy htpasswd, `add-user.sh`, rate-limited
  sign-in, branded sign-in page) while Entra ID needs tenant admin consent.
- `6febd6c` Describe password sign-in in the AKS docs and in the deploy script's output.

Details: [AKS deployment](../developer-guide/deployment/aks-deployment.md),
[Authentication](../developer-guide/authentication/index.md).

### Container Apps design

- `98e22f4` Prepare AMLens for deployment on Azure Container Apps: `infra/main.bicep`,
  `infra/deploy.ps1`, Dockerfiles for backend, RAG and frontend, the frontend's same-origin API
  proxy, the backend proxy-key check, `docker-compose.yml` for a production-like local run, the
  seed job, the first CI/CD workflow and `DEPLOY.md`. Also adds migration
  `0002_alert_status_backfill` (alert lifecycle `OPEN` → `UNDER REVIEW` → `DECIDED`) and the demo
  file `backend/examples/demo_wealth_book_nov2026.csv`. Not deployable in the sandbox; see
  [Container Apps design](../developer-guide/deployment/container-apps-design.md).

### Integration fixes

- `209825e` Read the agents' LLM and RAG settings from the environment.
- `a2b29b7` Align backend API responses with the frontend contract.
- `d690c2b` Make the frontend work against the live backend.
- `4ea87ee` Stop tracking compiled Python files and local databases.
- `88eb09d` Report the task queue as `not_applicable` instead of `degraded` in the health
  endpoint.
- `f35080e` Document how to run the full stack and fix stale backend setup steps.

### Retrieval quality

- `ac36a3f` Add human-verified guidance passages for `unusual_activity`, `rapid_movement` and
  `fan_in_out` (verbatim paragraphs from the RBI KYC Master Direction).
- `3a019da` Describe typologies in words and calibrate citation relevance (threshold 0.40 for
  `text-embedding-3-small`). See [Azure AI Search](../developer-guide/integrations/azure-ai-search.md#relevance-threshold).

## 2026-11-23: Integration of the member branches

- `e71d841` Merge pull request #1 (`feature/postgres-migration`): `2c1d7c7` migrates the main
  AML data from SQLite to PostgreSQL, with Alembic migrations.
- `15bd6df` Use Azure OpenAI as the default LLM provider for the agents module.
- `12f8747` Add the frontend (Next.js).
- `e8dd1cc` Add the Azure AI Search integration and the RAG evaluation script.
- `985bc65` Merge `member1-backend` into `integration`.
- `422f896` Merge `Member-2---RAG` into `integration`.
- `7cca049` Merge `feature/frontend` into `integration`.

## 2026-11-20: Core modules

- `5244439` Add the investigation agents module: LangGraph pipeline, report verifier,
  guardrails, SQLite store, Service Bus worker, mocks and tests.
- `8d153d0` Add the RAG corpus: the four guidance PDFs, extracted text, chunks and the local
  FAISS index ("Add files via upload").
- `449c28f` Backend: AML detection rules, SQLite integration and the agent-compatible
  `AlertBundle` adapter.

## 2026-11-19: Project start

- `94a70f7` First commit.

## Known open items

Tracked in [Security: known limitations](../developer-guide/security/index.md#known-limitations)
and [Monitoring](../developer-guide/monitoring/index.md#recommendations): Entra ID sign-in,
managed identity for AI services, point-in-time database recovery, central logging and alerting,
and asynchronous investigations.
