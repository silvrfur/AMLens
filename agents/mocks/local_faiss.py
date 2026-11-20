"""Optional toy index; not Member 2's production embedding or ingestion pipeline."""
import numpy as np
import faiss
from ..schemas.agent_outputs import RetrievalResult
from .sample_data import GUIDANCE

VOCAB = ('deposits', 'threshold', 'funds', 'transfers', 'counterparties', 'payments', 'review')
def embed(text):
    v = np.array([text.lower().count(w) for w in VOCAB], dtype='float32')
    norm = np.linalg.norm(v)
    return v / norm if norm else v

class LocalFAISSDemoClient:
    def search_aml_guidance(self, query, typology, top_k=5):
        chunks = [g for g in GUIDANCE if g['typology'] == typology]
        if not chunks: return RetrievalResult()
        index = faiss.IndexFlatIP(len(VOCAB))
        index.add(np.stack([embed(g['text']) for g in chunks]))
        scores, ids = index.search(embed(query)[None, :], min(top_k, len(chunks)))
        found = [{**chunks[int(i)], 'relevance_score': max(-1, min(1, float(s)))} for s, i in zip(scores[0], ids[0])]
        return RetrievalResult.model_validate({'retrieved_guidelines': found, 'source_references': [g['chunk_id'] for g in found], 'relevance_notes': ['Toy lexical embeddings only.']})
