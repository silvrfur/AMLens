---
audience: developer
---

# Monitoring

This page lists what you can observe in the production AKS deployment today, what is missing,
and what to add. Facts are labelled **Verified live** (read-only checks on 2026-11-25) or
**From repository**.

## What exists

### Health endpoints

| Endpoint | Served by | Returns | Used by |
|---|---|---|---|
| `GET /health` (backend, port 8000) | `backend/app/api/health.py` | `{"status","backend","agent","rag","queue","checked_at"}` | Kubernetes probes; the public health path below |
| `GET /api/backend/health` (public, no sign-in) | Frontend proxy → backend `/health` | Same JSON | **Settings → Service health** page, `deploy.sh` and `rollout.sh` smoke tests, external uptime checks |
| `GET /health` (RAG, port 8001) | `RAG/app/main.py` | `{"status":"healthy","search_backend":"azure"}` | Kubernetes probes |
| `GET /ping` (oauth2-proxy, port 4180) | oauth2-proxy | `OK` | Readiness probe |
| `pg_isready` (PostgreSQL) | exec probe | exit code | Readiness and liveness probes |

Verified live: `GET https://amlens-870b3a.southindia.cloudapp.azure.com/api/backend/health`
returned `200` with `backend`, `agent` and `rag` all `healthy` and `queue` `not_applicable`.

What the backend health fields mean:

| Field | `healthy` when | Otherwise |
|---|---|---|
| `backend` | `SELECT 1` on the database succeeds | `offline` |
| `agent` | The `agents` package is importable in the backend process | `offline` |
| `rag` | `USE_MOCK_RAG` is false and `GET $RAG_SERVICE_URL/health` returns 200 within 2 s | `degraded` (mock RAG) or `offline` |
| `queue` | always `not_applicable`: investigations run in-process, there is no Service Bus | — |

!!! warning "RAG health does not test Azure"
    The RAG `/health` endpoint does not call Azure OpenAI or AI Search. If the Search service is
    deleted or a key is wrong, health stays green while investigations fail at retrieval. A
    real end-to-end check needs a `/search` call (see recommendations).

### Kubernetes probes

From `deploy/aks/base/apps.yaml`, `postgres.yaml`, `edge.yaml` (backend values verified live):

| Workload | Readiness | Liveness |
|---|---|---|
| backend | `GET /health:8000` every 10 s | every 30 s, 5 failures |
| rag | `GET /health:8001` every 10 s | every 30 s |
| frontend | `GET /:3000` every 10 s | none |
| oauth2-proxy | `GET /ping:4180` every 10 s | none |
| postgres | `pg_isready` every 5 s | every 20 s, 6 failures |

Note that the backend liveness probe also runs `SELECT 1`; a database outage marks the backend
unready (removed from the Service) but it takes 5 × 30 s before a restart.

### Logs

Container stdout/stderr only, read with `kubectl logs` (commands in the
[runbook](../deployment/operations-runbook.md#view-logs)). Kubernetes keeps logs of the current
and the previous container instance per pod; they are lost when a pod is deleted or rescheduled.

| Component | What it logs |
|---|---|
| backend | Uvicorn access log; agent events as JSON lines (logger `traceiq`): `tool_attempt` with tool name, investigation id and count; audit events. No prompt contents or provider error messages |
| rag | Start-up (`AMLens active search backend: azure`), stack traces for failed searches |
| oauth2-proxy | Auth requests and sign-in attempts (success and failure) |
| NGINX (`app-routing-system/amlens-nginx-0`) | Access log for all public requests, including rate-limited ones |
| migrate / seed / backup jobs | Alembic output; loaded row counts; `uploaded amlens-<timestamp>.dump` |

### Application-level records

The database itself is an operational record: `agent_runtime.agent_runs` (per-node status,
timings, errors), `agent_runtime.tool_calls` (every external call attempt) and the audit tables
show what each investigation did. See [Database overview](../database/overview.md).

### Backup job status

Verified live: CronJob `postgres-backup` at `30 20 * * *` with last successful run
2026-11-24 20:30 UTC. Check with:

```bash
kubectl -n amlens get cronjob postgres-backup -o jsonpath='{.status.lastSuccessfulTime}'
kubectl -n amlens get jobs
```

Kubernetes keeps the last 3 successful and 3 failed backup jobs.

### Resource usage

Verified live: `kubectl top nodes` works (metrics-server is installed by AKS). On 2026-11-25 the
two nodes used about 10 % CPU and 65–70 % memory. Use `kubectl top pods -n amlens` for
per-pod figures.

### Certificates

```bash
kubectl -n amlens get certificate amlens-tls      # READY should be True
```

cert-manager renews the Let's Encrypt certificate automatically about 30 days before expiry.

## What does not exist

Verified live on 2026-11-25 unless stated:

- **No Azure Monitor / Container Insights:** no `ama-logs` or `omsagent` pods in `kube-system`,
  so no Log Analytics workspace receives container logs or metrics.
- **No alerting** of any kind (from repository: nothing in `deploy/aks/` creates alert rules,
  action groups or uptime tests).
- **No application metrics** endpoint (no Prometheus `/metrics`) and no tracing.
- **No log retention** beyond what the kubelet keeps on the node.
- **No uptime monitor** calling the public health endpoint (from repository; none configured).
- The Log Analytics workspace exists only in the undeployed
  [Container Apps design](../deployment/container-apps-design.md).

## Recommendations

In rough order of value for effort:

1. **External uptime check** on `https://<host>/api/backend/health` (Azure Monitor standard
   availability test, or any uptime service) alerting when the status is not 200 or any field is
   not `healthy`. The endpoint is public by design and returns no data.
2. **Deep RAG check.** Add a periodic synthetic `POST /search` (e.g. a Kubernetes CronJob inside
   the namespace, which the network policy would need to allow), or make the backend health
   optionally probe one search, so a deleted Search service or rotated key is noticed before an
   analyst hits it.
3. **Backup freshness alert.** Alert when `lastSuccessfulTime` of `postgres-backup` is older than
   26 hours, and when the backup SAS is within 30 days of its 365-day expiry.
4. **Enable Container Insights** (`az aks enable-addons -a monitoring`) with a Log Analytics
   workspace, if the subscription allows it, for log retention and queries over
   oauth2-proxy sign-in failures, backend errors and pod restarts.
5. **Alert on pod restarts and Pending pods** (the two B2s nodes are near their memory limit).
6. **Track Azure OpenAI 429s and AI Search errors** with metrics on those resources (Azure
   Monitor metrics are available on the resources without any cluster changes).
7. **Certificate expiry alert** as a safety net for cert-manager renewal failures.

## Daily checks (until alerting exists)

```bash
export KUBECONFIG=deploy/aks/.kubeconfig
curl -s https://<host>/api/backend/health
kubectl -n amlens get pods                     # all Running/Completed, low RESTARTS
kubectl -n amlens get cronjob postgres-backup  # LAST SCHEDULE within 24 h
kubectl -n amlens get certificate amlens-tls   # READY True
kubectl top nodes
```
