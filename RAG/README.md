
# AMLens — Member 2 FAISS RAG Backend

## Overview

This service provides AML regulatory guidance retrieval
using SentenceTransformer embeddings, FAISS and FastAPI.

It exposes an HTTP endpoint for Member 3's
AML Knowledge Retrieval Agent.

## Prerequisites

- Python and pip
- Internet access for the initial embedding model download
- The committed FAISS index and metadata files

## Installation

From the RAG directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Start the API

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Swagger documentation:
http://127.0.0.1:8000/docs

## Member 3 Integration

Endpoint: POST /search

Request:

```json
{
  "query": "What are the indicators of structuring transactions?",
  "typology": "structuring",
  "top_k": 5
}
```

Response fields:

- retrieved_guidelines
- source_references
- relevance_notes

Each guideline includes:
chunk_id, text, source, section, page,
typology and relevance_score.

For Member 3's HTTP adapter:

```env
USE_MOCK_RAG=false
RAG_SERVICE_URL=http://127.0.0.1:8000
```

The service must be running for HTTP requests to work.

## Current Implementation

- Embedding model: all-MiniLM-L6-v2
- Vector index: FAISS IndexFlatIP
- Normalized embeddings: Yes
- Hidden search retries: None
- Verified typology: structuring
- Other typologies: Pending verified annotations

## Known Limitations

- Retrieval quality is not fully calibrated.
- The verified structuring passage currently scores
  approximately 0.509 for the test query.
- A similarity threshold of 0.65 is not yet validated.
- Unsupported typologies may return empty results.
- Section and typology coverage is incomplete.
- Azure AI Search integration is pending.
- Azure OpenAI answer generation is pending.
- This API retrieves evidence; it does not generate
  investigation reports.

## Ownership

Member 2 — RAG and Machine Learning Engineering.
