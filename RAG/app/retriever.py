
import json
import faiss
import numpy as np

from pathlib import Path
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE_DIR / "indexes"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class AMLRetriever:

    def __init__(self):

        print("Loading embedding model...")
        self.model = SentenceTransformer(MODEL_NAME)

        print("Loading FAISS index...")
        self.index = faiss.read_index(
            str(INDEX_DIR / "aml_faiss.index")
        )

        print("Loading chunk metadata...")
        with open(
            INDEX_DIR / "aml_chunks_metadata.json",
            "r",
            encoding="utf-8"
        ) as f:
            self.metadata = json.load(f)

        print("Retriever initialized successfully!")

    def retrieve(self, question, top_k=5):

        if not question.strip():
            raise ValueError("Question cannot be empty")

        # Convert question into an embedding
        query_embedding = self.model.encode(
            [question],
            normalize_embeddings=True
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32"
        )

        # Search FAISS index
        scores, indices = self.index.search(
            query_embedding,
            top_k
        )

        results = []

        for score, idx in zip(scores[0], indices[0]):

            if idx < 0:
                continue

            chunk = self.metadata[idx]

            results.append({
                "document_name": chunk["document_name"],
                "page_number": chunk["page_number"],
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "similarity_score": float(score)
            })

        return results
