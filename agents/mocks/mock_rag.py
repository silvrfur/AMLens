from ..schemas.agent_outputs import RetrievalResult
from .sample_data import GUIDANCE

class MockRAGClient:
    def __init__(self): self.queries = []
    def search_aml_guidance(self, query, typology, top_k=5):
        self.queries.append((query, typology, top_k))
        chunks = [dict(g) for g in GUIDANCE if g['typology'] == typology][:top_k]
        return RetrievalResult.model_validate({
            'retrieved_guidelines': chunks,
            'source_references': [g['chunk_id'] for g in chunks],
            'relevance_notes': ['Illustrative offline fixtures, not authoritative regulatory guidance.']})
