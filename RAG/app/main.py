
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# AMLens imports. The FAISS pipeline (sentence-transformers, torch) is imported
# only when it is needed, so the Azure deployment image can leave it out.
from app.models import RetrievalResult


# ==========================================
# 1. Load environment variables
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=True)


# ==========================================
# 2. Initialize FastAPI
# ==========================================

app = FastAPI(
    title="AMLens Knowledge Retrieval API",
    description=(
        "AML regulatory knowledge retrieval "
        "using FAISS or Azure AI Search"
    ),
    version="1.1.0"
)

# Browser access for the frontend (e.g. RAG_CORS_ORIGINS=http://localhost:3000).
# Unset = no CORS headers, same as before.
allowed_origins = [o.strip() for o in os.getenv("RAG_CORS_ORIGINS", "").split(",") if o.strip()]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


# ==========================================
# 3. Local RAG pipeline (FAISS), created on first use
# ==========================================

_pipeline = None


def get_pipeline():
    """Load the local embedding model and FAISS index (slow; needs the full requirements)."""
    global _pipeline
    if _pipeline is None:
        from app.rag_pipeline import AMLRAGPipeline
        _pipeline = AMLRAGPipeline()
    return _pipeline


# ==========================================
# 4. Select retrieval backend
# ==========================================

print("\nInitializing AMLens RAG...")

RAG_BACKEND = os.getenv(
    "RAG_BACKEND", "faiss"
).strip().lower()

if RAG_BACKEND not in ("azure", "faiss"):
    raise ValueError(
        "RAG_BACKEND must be either 'azure' or 'faiss'"
    )

if RAG_BACKEND == "azure":

    print("Initializing Azure AI Search adapter...")

    from app.azure_search_adapter import TeamAzureSearchAdapter

    search_adapter = TeamAzureSearchAdapter()

    print("Azure AI Search adapter initialized!")

else:

    print("Using local FAISS adapter...")

    from app.team_faiss_adapter import TeamFAISSAdapter

    search_adapter = TeamFAISSAdapter(
        retriever=get_pipeline().retriever
    )

print(f"\nAMLens active search backend: {RAG_BACKEND}")


# ==========================================
# 5. Request models
# ==========================================

class AMLQuery(BaseModel):

    question: str = Field(
        min_length=1,
        description="AML-related question"
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20
    )


class AMLSearchRequest(BaseModel):

    query: str = Field(
        min_length=1,
        description="AML guidance search query"
    )

    typology: str = Field(
        min_length=1,
        description="AML typology, e.g. structuring"
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20
    )


# ==========================================
# 6. Home / Health endpoint
# ==========================================

@app.get("/")
def home():

    return {
        "message": (
            "AMLens Knowledge Retrieval API is running"
        ),
        "status": "healthy",
        "search_backend": RAG_BACKEND
    }


@app.get("/health")
def health():
    """Liveness/readiness probe. The search backend is set up at import time, so a
    running process is ready; no external service is called per probe."""

    return {
        "status": "healthy",
        "search_backend": RAG_BACKEND
    }


# ==========================================
# 7. Existing local RAG retrieval endpoint
# ==========================================

@app.post("/retrieve")
def retrieve_aml_knowledge(request: AMLQuery):

    try:
        pipeline = get_pipeline()
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail=(
                "/retrieve needs the local FAISS pipeline, which this "
                "deployment does not install; use /search"
            )
        )

    try:

        result = pipeline.run(
            request.question,
            top_k=request.top_k
        )

        return {
            "question": result["question"],
            "status": result["status"],
            "sources": result["sources"],
            "prompt_ready": result["prompt"] is not None
        }

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve AML knowledge"
        )


# ==========================================
# 8. Member 3 - Agent Integration Endpoint
# ==========================================

@app.post(
    "/search",
    response_model=RetrievalResult
)
def search_aml_guidance(request: AMLSearchRequest):

    try:

        # Uses Azure or FAISS based on .env
        result = search_adapter.search_aml_guidance(
            query=request.query,
            typology=request.typology,
            top_k=request.top_k
        )

        return result

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="AML guidance search failed"
        )
