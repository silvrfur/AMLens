from typing import Protocol
import httpx
from ..schemas.agent_outputs import RetrievalResult

class RAGClient(Protocol):
    def search_aml_guidance(self, query: str, typology: str, top_k: int = 5) -> RetrievalResult: ...

# INTEGRATION POINT — MEMBER 2 FAISS RAG
# Replace MockRAGClient with Member 2's actual FAISS retrieval service adapter.
# Preserve this request and response contract.
class HTTPRAGClient:
    """Thin synchronous adapter. Member 2 owns embeddings, indexing and ranking."""
    def __init__(self, base_url, client=None):
        self.base_url = base_url.rstrip('/')
        self.client = client or httpx.Client(timeout=20)

    def search_aml_guidance(self, query, typology, top_k=5):
        response = self.client.post(self.base_url + '/search', json={
            'query': query, 'typology': typology, 'top_k': top_k})
        response.raise_for_status()
        return RetrievalResult.model_validate(response.json())

    def close(self): self.client.close()
