import numpy as np
from app.typology_annotations import VERIFIED_CHUNKS
from pydantic import BaseModel, Field

from app.retriever import AMLRetriever


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


class TeamFAISSAdapter:

    def __init__(self, retriever=None):
        self.retriever = retriever or AMLRetriever()

        self.chunk_lookup = {
            chunk["chunk_id"]: (i, chunk)
            for i, chunk in enumerate(self.retriever.metadata)
        }

    def search_aml_guidance(
        self,
        query: str,
        typology: str,
        top_k: int = 5
    ) -> RetrievalResult:

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query cannot be empty")

        if not isinstance(typology, str) or not typology.strip():
            raise ValueError("Typology cannot be empty")

        if not isinstance(top_k, int) or not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")

        typology = typology.strip().lower()

        # Exactly one FAISS search, with no retries.
        faiss_results = self.retriever.retrieve(
            question=query,
            top_k=max(10, top_k)
        )

        faiss_hits = {
            item["chunk_id"]: item
            for item in faiss_results
        }

        verified = VERIFIED_CHUNKS.get(typology, {})

        guidelines = []
        notes = []
        query_vector = None

        for chunk_id, annotation in verified.items():

            match = self.chunk_lookup.get(chunk_id)

            if match is None:
                notes.append(
                    f"Verified chunk {chunk_id} is missing "
                    "from the FAISS index."
                )
                continue

            index_position, chunk = match

            if chunk_id in faiss_hits:
                score = faiss_hits[chunk_id]["similarity_score"]

            else:
                # Score a verified source chunk directly.
                # This is not another FAISS search.
                if query_vector is None:
                    query_vector = np.asarray(
                        self.retriever.model.encode(
                            [query],
                            normalize_embeddings=True
                        )[0],
                        dtype="float32"
                    )

                stored_vector = self.retriever.index.reconstruct(
                    index_position
                )

                score = float(
                    np.dot(query_vector, stored_vector)
                )

            guidelines.append(
                Guideline(
                    chunk_id=chunk_id,
                    text=chunk["text"],
                    source=chunk["document_name"],
                    section=annotation["section"],
                    page=chunk["page_number"],
                    typology=typology,
                    relevance_score=max(-1.0, min(1.0, score))
                )
            )

        guidelines.sort(
            key=lambda item: item.relevance_score,
            reverse=True
        )

        guidelines = guidelines[:top_k]

        if not guidelines:
            notes.append(
                f"No verified guidance chunks are currently "
                f"annotated for typology '{typology}'."
            )
        else:
            notes.append(
                "Results are limited to manually verified "
                "typology annotations; coverage is incomplete."
            )

        return RetrievalResult(
            retrieved_guidelines=guidelines,
            source_references=[
                item.chunk_id for item in guidelines
            ],
            relevance_notes=notes
        )
