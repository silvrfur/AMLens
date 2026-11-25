---
audience: developer
---

# Azure OpenAI

AMLens uses Azure OpenAI for two things:

| Use | Deployment (production) | Caller | Code |
|---|---|---|---|
| Report narrative (structured JSON chat completion) | `gpt-4.1-mini` | Agents, inside the backend process | `agents/services/azure_openai_llm.py` |
| Query embeddings for guidance search | `text-embedding-3-small` (1536 dimensions) | RAG service | `RAG/app/azure_search_adapter.py` |

Both deployment names in the production ConfigMap `amlens-config` were **verified live** on
2026-11-25. Index-time embeddings are created with the same embedding deployment by
`RAG/scripts/upload_azure_chunks.py` (see [Azure AI Search](azure-ai-search.md)).

## Configuration

| Variable | Used by | Production value / source |
|---|---|---|
| `LLM_PROVIDER` | agents | `azure_openai` (default; `groq` is the alternative) |
| `USE_MOCK_LLM` | agents | `false` in production. **Defaults to `true`** in `agents/config.py`, so local runs use the offline mock unless you turn it off |
| `AZURE_OPENAI_ENDPOINT` | agents | `https://<openai-account>.openai.azure.com/` (ConfigMap) |
| `AZURE_OPENAI_DEPLOYMENT` | agents | `gpt-4.1-mini` (ConfigMap) |
| `AZURE_OPENAI_API_VERSION` | agents | Not set in production, so the default `2024-10-21` applies. Set it to `v1` (or use an endpoint ending in `/openai/v1`) to use the v1 API |
| `AZURE_OPENAI_API_KEY` | agents, RAG | Secret `amlens-ai` (`key1` of the account). Empty = Entra ID authentication |
| `AZURE_OPENAI_BASE_URL` | RAG, index scripts | `https://<openai-account>.openai.azure.com/openai/v1/` (ConfigMap) |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | RAG, index scripts | `text-embedding-3-small` (ConfigMap) |
| `LLM_TIMEOUT_SECONDS` | agents | Default 30 s (allowed range above 0, up to 60) |

`deploy.sh` finds the account automatically: the first `OpenAI`/`AIServices` account in the
resource group that has a deployment named `gpt-4.1-mini` (override with `OPENAI=<account>` and
`CHAT_DEPLOYMENT=`, `EMBEDDING_DEPLOYMENT=`). The full variable list is in
[Configuration](../getting-started/configuration.md).

## Chat client (agents)

`create_llm()` in `agents/main.py` builds the client lazily, so only the configured provider's
SDK must be installed:

- `USE_MOCK_LLM=true` → `MockGroqClient` (offline, deterministic).
- `LLM_PROVIDER=azure_openai` → `AzureOpenAILLM`.
- `LLM_PROVIDER=groq` → `GroqLLM` (`GROQ_API_KEY`, `GROQ_MODEL`), same contract.

`AzureOpenAILLM` picks the API flavour from the settings:

| Condition | Client |
|---|---|
| `api_version == "v1"` or endpoint ends with `/openai/v1` | `openai.OpenAI(base_url=<endpoint>/openai/v1/)` |
| otherwise (production: `2024-10-21`) | `openai.AzureOpenAI(azure_endpoint=..., api_version=...)` |

Authentication: the API key if set; otherwise an Entra ID bearer-token provider from
`DefaultAzureCredential` for scope `https://cognitiveservices.azure.com/.default` (managed
identity in Azure, `az login` locally). The identity then needs the role
*Cognitive Services OpenAI User*. Production uses the key, because the sandbox does not allow the
role assignment.

### Request contract

`generate_structured_response(system_prompt, user_input, response_schema)`:

- System message = the agent's prompt + `"Return only JSON matching this schema: <JSON schema>"`
  generated from the Pydantic model.
- User message = `json.dumps(user_input)`: for the report agent this is the minimal payload from
  `safe_llm_payload()` (investigation id, allowed statements, allowed next steps), never raw
  transaction descriptions or retrieved passages.
- `temperature=0`, `response_format={"type": "json_object"}`.
- The response is validated locally with `response_schema.model_validate_json(...)`.

### Failure handling

| Situation | Behaviour |
|---|---|
| `RateLimitError` (429), `APIConnectionError`, timeout | Retried, up to 3 attempts in total, with back-off 1 s, 2 s |
| `APIStatusError` 5xx | Retried the same way |
| `APIStatusError` 4xx (bad key, missing deployment, content filter) | Not retried; raises `LLMUnavailable` |
| Invalid JSON / schema mismatch | `ValidationError` propagates; the graph's single correction route handles it, and the run ends `incomplete` if the report still fails verification |

SDK-level retries are disabled (`max_retries=0`) so that **every** real request is charged to
the investigation's tool budget (`consume("llm.generate")`, at most 8 external calls per
investigation). Provider exception messages and prompt contents are not logged.

When the LLM is unavailable the investigation fails and the analyst can retry it from the
investigation page (see the user guide's [retry workflow](../../user-guide/workflows/retry-failed-investigation.md)).

## Embedding client (RAG)

`TeamAzureSearchAdapter` creates `openai.OpenAI(base_url=AZURE_OPENAI_BASE_URL, ...)` with
`timeout=60`, `max_retries=0`. It uses the key if `AZURE_OPENAI_API_KEY` is set, otherwise an
Entra ID token provider. Each `/search` call creates one embedding for the query and checks that
it has exactly 1536 dimensions before querying the index.

## Operations

- **Rotate the key:** regenerate `key1` and re-run `deploy.sh`, which reads the key from Azure
  on every run; then the backend and RAG pods restart with the new value. See
  [Rotate keys and secrets](../deployment/operations-runbook.md#rotate-keys-and-secrets).
- **Change the model:** create a new deployment in the account, then re-run `deploy.sh` with
  `CHAT_DEPLOYMENT=<name>` (and note that the account auto-discovery looks for that name).
  Changing the **embedding** model requires re-embedding the whole index and re-calibrating the
  relevance threshold (see [Azure AI Search](azure-ai-search.md#relevance-threshold)).
- **Quota:** `gpt-4.1-mini` tokens-per-minute quota is set on the deployment in Azure. 429
  responses appear as failed investigations; check backend logs.

## Local development

In `backend/.env`:

```bash
USE_MOCK_LLM=false
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://<openai-account>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_API_KEY=<key>          # or leave empty and run `az login`
```

Keep keys only in git-ignored `.env` files.
