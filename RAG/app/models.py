"""Response models shared by both search backends.

Kept free of FAISS / sentence-transformers imports so the Azure backend can run
without installing them.
"""
from pydantic import BaseModel, Field


class Guideline(BaseModel):
    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    section: str
    page: int | None = Field(default=None, ge=1)
    typology: str
    relevance_score: float = Field(ge=-1, le=1)


class RetrievalResult(BaseModel):
    retrieved_guidelines: list[Guideline] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    relevance_notes: list[str] = Field(default_factory=list)
