
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.team_faiss_adapter import TeamFAISSAdapter, RetrievalResult

from app.rag_pipeline import AMLRAGPipeline


app = FastAPI(
    title="AMLens Knowledge Retrieval API",
    description="API for retrieving AML regulatory knowledge",
    version="1.0.0"
)
# Initialize the RAG pipeline
pipeline = AMLRAGPipeline()

# Initialize adapter for Member 3's agent
faiss_adapter = TeamFAISSAdapter(
    retriever=pipeline.retriever
)

class AMLQuery(BaseModel):
    question: str = Field(
        min_length=1,
        description="AML-related question"
    )
    top_k: int = Field(default=5, ge=1, le=20)


@app.get("/")
def home():
    return {
        "message": "AMLens Knowledge Retrieval API is running"
    }


@app.post("/retrieve")
def retrieve_aml_knowledge(request: AMLQuery):

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
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve AML knowledge"
        )



class AMLSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    typology: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@app.post("/search", response_model=RetrievalResult)
def search_aml_guidance(request: AMLSearchRequest):

    try:
        return faiss_adapter.search_aml_guidance(
            query=request.query,
            typology=request.typology,
            top_k=request.top_k
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception:
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="AML guidance search failed"
        )