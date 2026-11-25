---
audience: developer
---

# RAG API

The RAG service (`RAG/app/main.py`, FastAPI title `AMLens Knowledge Retrieval API`, version `1.1.0`)
returns verified AML guidance passages for a query and a typology. Two clients use it:

- **The agents.** The retrieval agent calls `POST {RAG_SERVICE_URL}/search` through `agents/services/rag_client.py`. In production, `RAG_SERVICE_URL=http://rag:8001`.
- **The frontend's knowledge base page.** It calls `POST /api/rag/search` through the same-origin proxy (see [API reference overview](overview.md)).

| | |
|---|---|
| Port | `8001` (`RAG/Dockerfile`, Kubernetes Service `rag`) |
| Public path | `/api/rag/<path>`, sign-in required on the live site |
| Authentication | None in the app. It is internal-only: a ClusterIP Service, and the `rag-from-app` NetworkPolicy admits only the backend and frontend pods. It does not check `X-AMLens-Proxy-Key`. |
| CORS | Only if `RAG_CORS_ORIGINS` is set (methods `GET` and `POST`, header `Content-Type`) |

## Search backends

`RAG_BACKEND` is read once at startup. Any value other than `azure` or `faiss` stops the app from
starting.

| `RAG_BACKEND` | Adapter | Used in | Notes |
|---|---|---|---|
| `azure` (the image default) | `TeamAzureSearchAdapter` (`RAG/app/azure_search_adapter.py`) | Production | One vector query against Azure AI Search (`content_vector` field, 1536-dimension `text-embedding-3-small` embeddings), pre-filtered by `typology eq '<typology>'`. Results below a **0.40** cosine similarity are dropped. |
| `faiss` (the code default when unset) | `TeamFAISSAdapter` (`RAG/app/team_faiss_adapter.py`) | Local only | Needs `requirements.txt` (sentence-transformers, torch, FAISS) and `RAG/indexes`. Returns only the chunks that are manually annotated for the typology in `typology_annotations.py`, scored against the query. |

Azure settings (names only): `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`,
`AZURE_OPENAI_API_KEY` (optional), `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_INDEX_NAME` and
`AZURE_SEARCH_ADMIN_KEY` (optional). If either key is unset, `DefaultAzureCredential` is used:
managed identity in Azure (set `AZURE_CLIENT_ID` for a user-assigned identity) or `az login`
locally. The identity needs the "Cognitive Services OpenAI User" and "Search Index Data Reader"
roles. For more, see [Azure AI Search](../integrations/azure-ai-search.md).

### The 0.40 relevance cutoff

Azure AI Search returns `@search.score`. The adapter converts it to cosine similarity with
`similarity = 2 - 1/score`, clamps the result to −1 to 1, and keeps a result only if
`similarity >= 0.40`. The cutoff was calibrated on 2026-11-24 with `text-embedding-3-small`, within
the typology pre-filter:

| Query kind | Observed similarity |
|---|---|
| The agents' descriptive queries | 0.46 – 0.66 |
| Other AML topics (for example onboarding) | 0.27 – 0.37 |
| Unrelated text | ≤ 0.12 |

The previous cutoff of 0.50 dropped every agent query. Check these ranges again if the embedding
model or the corpus changes.

### Typology values

`typology` is free text in the request schema. It is trimmed and lowercased, and only passages
tagged with exactly that typology are returned. An unknown typology is **not** an error: the
response is `200` with an empty `retrieved_guidelines` and an explanatory `relevance_note`. The
verified typology keys come from `VERIFIED_CHUNKS` in `RAG/app/typology_annotations.py`:

| Typology | Verified chunk IDs |
|---|---|
| `structuring` | `RBI_KYC_Master_Direction_p23_structuring_1` |
| `unusual_activity` | `RBI_KYC_Master_Direction_p40_unusual_activity_1`, `FIU_Guidance_p10_unusual_activity_1`, `FATF_Recommendations_p73_unusual_activity_1` |
| `rapid_movement` | `RBI_KYC_Master_Direction_p40_rapid_movement_1` |
| `fan_in_out` | `RBI_KYC_Master_Direction_p41_fan_in_out_1` |
| `customer_due_diligence` | `RBI_KYC_Master_Direction_p11_c2` |
| `enhanced_due_diligence` | `FIU_Guidance_p10_c1` |
| `ongoing_monitoring` | `RBI_KYC_Master_Direction_p40_c1` |
| `suspicious_transaction_reporting` | `FATF_Recommendations_p20_c2` |
| `money_mules` | `RBI_KYC_Master_Direction_p64_c1` |

The table lists the annotations used by the FAISS adapter. The Azure adapter filters on the
`typology` field stored in the Azure AI Search index. `RAG/scripts/update_azure_typologies.py`
writes that field from the same `VERIFIED_CHUNKS` annotations.

The agents only ever send the four alert typologies (`structuring`, `rapid_movement`,
`fan_in_out` and `unusual_activity`), and the frontend's `Typology` type offers the same four.

## Endpoints

Throughout this page, `$RAG_URL` is the service base URL, for example `http://127.0.0.1:8001`.

### Service info

`GET /` · public path `GET /api/rag/` (sign-in required)

**Response `200`**

| Field | Type | Value |
|---|---|---|
| `message` | string | `AMLens Knowledge Retrieval API is running` |
| `status` | string | `healthy` |
| `search_backend` | string | `azure` or `faiss` |

=== "curl"

    ```bash
    curl -s "$RAG_URL/"
    ```

=== "Response"

    ```json
    {"message": "AMLens Knowledge Retrieval API is running", "status": "healthy", "search_backend": "azure"}
    ```

### Health

`GET /health` · public path `GET /api/rag/health` (sign-in required)

A liveness and readiness probe. The search backend is set up at import time, so the probe makes
no external call. The backend's `/health` uses this endpoint to report `rag: healthy`.

**Response `200`:** `{"status": "healthy", "search_backend": "azure" | "faiss"}`

=== "curl"

    ```bash
    curl -s "$RAG_URL/health"
    ```

=== "Response"

    ```json
    {"status": "healthy", "search_backend": "azure"}
    ```

### Search AML guidance

`POST /search` · public path `POST /api/rag/search` (sign-in required)

The agent integration endpoint. Declared with `response_model=RetrievalResult`.

**Request body:** `AMLSearchRequest`

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `query` | string | yes | | `min_length=1`, must not be blank |
| `typology` | string | yes | | `min_length=1`, must not be blank, lowercased |
| `top_k` | integer | no | `5` | 1–20 |

**Response `200`:** `RetrievalResult`

| Field | Type | Description |
|---|---|---|
| `retrieved_guidelines` | `Guideline[]` | At most `top_k` passages, each with `chunk_id`, `text`, `source`, `section`, `page` (int or null, ≥ 1), `typology`, `relevance_score` (−1 to 1) |
| `source_references` | string[] | The `chunk_id` of each returned guideline, in the same order |
| `relevance_notes` | string[] | Caveats about coverage. They always say that results are limited to verified annotations, or that nothing relevant was found. |

| Status | `detail` | Cause |
|---|---|---|
| `200` | | Including empty results |
| `400` | `Query cannot be empty`, `Typology cannot be empty`, `top_k must be between 1 and 20`, `Embedding dimension mismatch`, `Invalid Azure search score` | `ValueError` from the adapter (whitespace-only input, or an unexpected embedding or score) |
| `422` | validation list | Missing field, empty string, or `top_k` out of range |
| `500` | `AML guidance search failed` | Any other error, for example Azure OpenAI or AI Search unavailable or not authorized |

=== "curl"

    ```bash
    curl -s -X POST "$RAG_URL/search" \
      -H "Content-Type: application/json" \
      -d '{"query": "funds moved through an intermediary account within an hour", "typology": "rapid_movement", "top_k": 5}'
    ```

=== "Response"

    ```json
    {
      "retrieved_guidelines": [
        {
          "chunk_id": "RBI_KYC_Master_Direction_p40_rapid_movement_1",
          "text": "(passage text from the approved corpus)",
          "source": "RBI_KYC_Master_Direction",
          "section": "Chapter VI - Customer Due Diligence (CDD) Procedure, E. On-going Due Diligence, Paragraph 40",
          "page": 40,
          "typology": "rapid_movement",
          "relevance_score": 0.5731
        }
      ],
      "source_references": ["RBI_KYC_Master_Direction_p40_rapid_movement_1"],
      "relevance_notes": [
        "Results are restricted to verified typology annotations. Other guidance chunks are not yet classified."
      ]
    }
    ```

=== "Response (no match)"

    ```json
    {
      "retrieved_guidelines": [],
      "source_references": [],
      "relevance_notes": [
        "No sufficiently relevant verified guidance was found for typology 'fan_in_out'. Typology coverage and relevance calibration are still incomplete."
      ]
    }
    ```

### Retrieve (local FAISS pipeline)

`POST /retrieve` · public path `POST /api/rag/retrieve` (sign-in required)

The older free-question retrieval route over the whole local FAISS index, with no typology filter.
It needs the FAISS pipeline (`requirements.txt`). The production image installs only
`requirements-azure.txt`, so **in production this route always returns `503`**. Use `/search` instead.

**Request body:** `AMLQuery`

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `question` | string | yes | | `min_length=1` |
| `top_k` | integer | no | `5` | 1–20 |

**Response `200`**

| Field | Type | Description |
|---|---|---|
| `question` | string | Echo of the question |
| `status` | string | `context_retrieved` or `no_relevant_context` |
| `sources` | array | Raw FAISS hits: `{document_name, page_number, chunk_id, text, similarity_score}` |
| `prompt_ready` | boolean | Whether a RAG prompt was built (that is, there were sources) |

| Status | `detail` | Cause |
|---|---|---|
| `200` | | |
| `400` | `Question cannot be empty` | Whitespace-only question |
| `422` | validation list | Invalid body |
| `500` | `Unable to retrieve AML knowledge` | Unexpected error |
| `503` | `/retrieve needs the local FAISS pipeline, which this deployment does not install; use /search` | FAISS and sentence-transformers are not installed (the Azure image) |

=== "curl"

    ```bash
    curl -s -X POST "$RAG_URL/retrieve" \
      -H "Content-Type: application/json" \
      -d '{"question": "What is structuring?", "top_k": 3}'
    ```

=== "Response (FAISS installed)"

    ```json
    {
      "question": "What is structuring?",
      "status": "context_retrieved",
      "sources": [
        {
          "document_name": "RBI_KYC_Master_Direction",
          "page_number": 23,
          "chunk_id": "RBI_KYC_Master_Direction_p23_structuring_1",
          "text": "(passage text)",
          "similarity_score": 0.61
        }
      ],
      "prompt_ready": true
    }
    ```

=== "Response (production)"

    ```json
    {"detail": "/retrieve needs the local FAISS pipeline, which this deployment does not install; use /search"}
    ```

For how the index is built and annotated, see [RAG service](../modules/rag-service.md).
