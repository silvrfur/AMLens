
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from app.team_faiss_adapter import Guideline, RetrievalResult


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)


class TeamAzureSearchAdapter:

    def __init__(self):

        self.openai_client = OpenAI(
            base_url=os.environ["AZURE_OPENAI_BASE_URL"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            timeout=60.0,
            max_retries=0
        )

        self.search_client = SearchClient(
            endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
            index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
            credential=AzureKeyCredential(
                os.environ["AZURE_SEARCH_ADMIN_KEY"]
            ),
            retry_total=0
        )

        # Provisional cutoff for initial testing.
        # Calibrate this using retrieval evaluation cases.
        self.min_score = 0.50

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

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or not 1 <= top_k <= 20
        ):
            raise ValueError("top_k must be between 1 and 20")

        typology = typology.strip().lower()

        # 1. Generate query embedding
        embedding_response = (
            self.openai_client.embeddings.create(
                model=os.environ[
                    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
                ],
                input=query
            )
        )

        query_vector = embedding_response.data[0].embedding

        if len(query_vector) != 1536:
            raise ValueError("Embedding dimension mismatch")

        # 2. Perform ONE Azure vector search
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="content_vector",
            kind="vector"
        )

        # Escape OData string values safely.
        safe_typology = typology.replace("'", "''")

        results = self.search_client.search(
            search_text=None,
            vector_queries=[vector_query],
            filter=f"typology eq '{safe_typology}'",
            vector_filter_mode="preFilter",
            select=[
                "chunk_id",
                "text",
                "source",
                "section",
                "page",
                "typology"
            ],
            top=top_k
        )

        guidelines = []
        notes = []

        # 3. Convert verified results into Member 3's schema
        for result in results:

            # Reject incorrectly tagged or incomplete metadata
            if result.get("typology") != typology:
                continue

            if not all(
                result.get(field)
                for field in ("chunk_id", "text", "source", "section")
            ):
                notes.append(
                    "A result with incomplete source metadata "
                    "was excluded."
                )
                continue

            raw_score = float(result["@search.score"])

            if raw_score <= 0:
                raise ValueError("Invalid Azure search score")

            # Valid for a single cosine vector query.
            similarity = 2.0 - (1.0 / raw_score)
            similarity = max(-1.0, min(1.0, similarity))

            if similarity < self.min_score:
                continue

            guidelines.append(
                Guideline(
                    chunk_id=result["chunk_id"],
                    text=result["text"],
                    source=result["source"],
                    section=result["section"],
                    page=result.get("page"),
                    typology=result["typology"],
                    relevance_score=similarity
                )
            )

        if not guidelines:
            notes.append(
                "No sufficiently relevant verified guidance "
                f"was found for typology '{typology}'. "
                "Typology coverage and relevance calibration "
                "are still incomplete."
            )
        else:
            notes.append(
                "Results are restricted to verified typology "
                "annotations. Other guidance chunks are not "
                "yet classified."
            )

        return RetrievalResult(
            retrieved_guidelines=guidelines,
            source_references=[
                guideline.chunk_id
                for guideline in guidelines
            ],
            relevance_notes=notes
        )
