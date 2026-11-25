---
audience: developer
---

# API reference overview

AMLens is built from three HTTP services. This section documents every route that the code
defines. The reference was produced by reading the route handlers and checked against the
OpenAPI document that FastAPI generates offline from `backend/app/main.py` and `agents/main.py`.

| Service | Source | FastAPI title / version | Port in production | Deployed? |
|---|---|---|---|---|
| Backend | `backend/app/main.py`, `backend/app/api/*.py` | `AML Member 1 Backend (MVP)` / `0.3.0` | 8000 (`backend` Service) | Yes |
| RAG (knowledge retrieval) | `RAG/app/main.py` | `AMLens Knowledge Retrieval API` / `1.1.0` | 8001 (`rag` Service) | Yes |
| Agents API | `agents/main.py`, `agents/api/routes.py` | `AMLens / TraceIQ Investigation Assistant` / `0.1.0` | none | **No.** It is a standalone app for local use. In production the backend imports the `agents` package and runs it in-process. See [Agents API](agents-api.md). |

The pages in this section:

- [Backend endpoints](endpoints.md): the 12 backend routes for uploads, alerts, transactions, investigations, decisions, audit history and health.
- [Schemas](schemas.md): every request and response model, including the investigation report structure.
- [Agents API](agents-api.md): the standalone agents app, and how the backend calls the agents in production.
- [RAG API](rag-api.md): guidance search (`/search`), health and the local FAISS `/retrieve` route.

## How requests reach the services

Browsers never call the backend or RAG directly. The only public component is the Next.js
frontend. It has a same-origin proxy route at `frontend/app/api/[service]/[...path]/route.ts`:

| Public path (browser) | Forwarded to | Environment variable on the frontend | Production value |
|---|---|---|---|
| `/api/backend/<path>` | `AMLENS_BACKEND_URL/<path>` | `AMLENS_BACKEND_URL` | `http://backend:8000` |
| `/api/rag/<path>` | `AMLENS_RAG_URL/<path>` | `AMLENS_RAG_URL` | `http://rag:8001` |

For example, the browser calls `GET /api/backend/alerts?limit=25&offset=0`, and the backend
receives it as `GET /alerts?limit=25&offset=0`. In this reference each endpoint lists both the
internal service path and the public proxied path.

The proxy:

- accepts `GET`, `POST`, `PUT`, `PATCH` and `DELETE`. The backend and RAG services define only `GET` and `POST` routes.
- URL-encodes every path segment again, so `..`, `/` or `?` inside a segment cannot escape the upstream path. The query string is passed through unchanged.
- forwards only the `Accept` and `Content-Type` request headers. Cookies and sign-in tokens are never forwarded.
- adds `X-AMLens-Proxy-Key: <AMLENS_PROXY_KEY>` when that variable is set.
- adds `X-AMLens-User: <signed-in user>`, taken from the first of these headers that is present: `X-MS-CLIENT-PRINCIPAL-NAME` (Azure Container Apps Easy Auth), `X-Auth-Request-Email`, or `X-Auth-Request-User`. On AKS, ingress-nginx sets the last two from oauth2-proxy and overwrites any copy the client sends.
- returns only the `Content-Type`, `Content-Disposition` and `Cache-Control` response headers, and passes the upstream status code through unchanged.
- returns its own errors:

| Status | Body | When |
|---|---|---|
| `404` | `{"detail": "Service '<service>' is not configured on this server."}` | `<service>` is not `backend` or `rag`, or its URL variable is unset. |
| `502` | `{"detail": "The <service> service is unreachable."}` | The upstream connection failed. |

The frontend client (`frontend/lib/api/client.ts`) uses `/api/backend` and `/api/rag` by
default. `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_RAG_BASE_URL` override these values, and
`NEXT_PUBLIC_USE_MOCKS` (mock data unless set to `false`) skips the network completely. For more
detail, see [Frontend proxy](../modules/frontend-proxy.md).

## Authentication

Authentication has two layers. For the full model, see [Authentication](../authentication/index.md).

**1. Sign-in at the edge (live site).** On AKS, the ingress (`deploy/aks/base/edge.yaml`) sends
every request through oauth2-proxy (`nginx.ingress.kubernetes.io/auth-url`). Unauthenticated
requests are redirected to `/oauth2/sign_in`. The only exception is an `Exact` ingress rule for
**`/api/backend/health`**, which can be reached without sign-in for the pipeline smoke test and
uptime checks. Every other public path, including all of `/api/rag/*`, requires a signed-in
session.

**2. Proxy key on the backend.** `backend/app/security.py` registers an HTTP middleware, `require_proxy`:

- If `AML_PROXY_KEY` is set on the backend, every request must carry an `X-AMLens-Proxy-Key` header whose value matches it. The comparison uses `hmac.compare_digest`. A missing or wrong key returns `401 {"detail": "Not authenticated"}`.
- `/health` is always open (`OPEN_PATHS = {'/health'}`), and `OPTIONS` requests (CORS preflight) are never checked.
- When the key matches, `X-AMLens-User` is trusted and stored as `request.state.user`. The decision endpoint records this value as `analyst_id` instead of the value in the request body.
- If `AML_PROXY_KEY` is unset, the check is off. This is local development mode, and every request is accepted.

In production, `AML_PROXY_KEY` (backend) and `AMLENS_PROXY_KEY` (frontend) both come from the
`AML_PROXY_KEY` key of the `amlens-app` Kubernetes Secret.

The RAG service has **no** application-level authentication. It is protected only by being
internal: it is a ClusterIP Service, and the `rag-from-app` NetworkPolicy admits traffic only
from the backend and frontend pods. Likewise, `backend-from-frontend` admits traffic to the
backend only from the frontend pod.

!!! note "FastAPI's built-in documentation routes"
    All three apps keep FastAPI's defaults: `/docs`, `/redoc` and `/openapi.json`. On the
    backend these are **not** in `OPEN_PATHS`, so they need the proxy key when `AML_PROXY_KEY`
    is set. On the live site they are reachable only after sign-in, at `/api/backend/docs`,
    `/api/rag/docs` and so on.

## CORS

Neither service sends CORS headers unless it is configured to, and the proxy makes CORS
unnecessary in deployments.

| Service | Variable | Allowed methods | Allowed headers |
|---|---|---|---|
| Backend | `AML_CORS_ORIGINS` (comma-separated, never `*`) | `GET`, `POST` | `Content-Type`, `Authorization` (credentials off) |
| RAG | `RAG_CORS_ORIGINS` (comma-separated) | `GET`, `POST` | `Content-Type` |

The backend registers its CORS middleware outside the proxy-key middleware. A `401` therefore
still carries CORS headers during local cross-origin development.

## Calling the API

The curl examples in this reference use these placeholders. Never paste real values into
documentation, tickets or chat.

| Placeholder | Meaning |
|---|---|
| `$AMLENS_URL` | Base URL of the backend service, for example `http://127.0.0.1:8000` locally |
| `$RAG_URL` | Base URL of the RAG service, for example `http://127.0.0.1:8001` locally |
| `$PROXY_KEY` | The value of `AML_PROXY_KEY`. Omit the header if the key is unset locally. |
| `$AMLENS_SITE` | Public site origin (`https://<host>`), used only with a signed-in browser session |

```bash
# Internal / local: call the service directly with the proxy key.
curl -s "$AMLENS_URL/alerts?limit=5" -H "X-AMLens-Proxy-Key: $PROXY_KEY"

# Public, without sign-in: only the health status is reachable.
curl -s "$AMLENS_SITE/api/backend/health"
```

Every other public path needs the oauth2-proxy session cookie from a signed-in browser. Scripts
should call the services from inside the cluster or local environment rather than reuse browser
sessions.

## Conventions

- **Content type.** Requests and responses are JSON (`application/json`). The CSV upload is the exception: it uses `multipart/form-data`.
- **Errors.** Handled errors use FastAPI's shape, `{"detail": "<message>"}`. Request validation failures (wrong types, a body that fails the Pydantic constraints) return `422` with `{"detail": [{"type", "loc", "msg", "input", ...}]}`. The frontend client displays `detail` in a toast when it is a string.
- **Pagination.** `GET /alerts` and `GET /investigations` take `limit` (1–200, default 50) and `offset` (≥ 0, default 0). An out-of-range value returns `400 {"detail": "Invalid pagination"}`, not `422`. Only `/alerts` returns a total count.
- **Identifiers.** Transaction, alert and dataset IDs are generated from the dataset hash (`TX_<dataset_id>_<row>`, `AL_<dataset_id>_<n>`). Investigation, decision and audit event IDs are UUID4 strings. Account identifiers never appear in clear text. They are HMAC tokens of the form `ACC_<24 hex>` (see [Database schema](../database/schema.md)).
- **Timestamps.** System timestamps are ISO 8601 in UTC (`...+00:00`). Transaction timestamps come from the source file and have no time zone. `AML_SOURCE_TIMEZONE` says which zone they are in.
- **Money.** Amounts are returned as decimal **strings**, never floats.
- **Versioning.** The API has no version prefix. The backend and the frontend are released together (see [AKS deployment](../deployment/aks-deployment.md)).
