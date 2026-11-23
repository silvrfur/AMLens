
import json
import numpy as np
import faiss
from pathlib import Path
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE_DIR / "indexes"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

FAISS_PATH = INDEX_DIR / "aml_faiss.index"
METADATA_PATH = INDEX_DIR / "aml_chunks_metadata.json"


def main():

    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    print("Loading FAISS index...")
    index = faiss.read_index(str(FAISS_PATH))

    print("Loading chunk metadata...")
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    query = input("\nEnter your AML question: ").strip()

    if not query:
        print("Please enter a valid question.")
        return

    # Convert question into an embedding
    query_vector = model.encode(
        [query],
        normalize_embeddings=True
    )

    query_vector = np.asarray(query_vector, dtype="float32")

    # Search for the top 5 matching chunks
    k = min(5, index.ntotal)
    scores, indices = index.search(query_vector, k)

    print("\n========== SEARCH RESULTS ==========")

    for rank, (score, idx) in enumerate(
        zip(scores[0], indices[0]), start=1
    ):

        if idx < 0:
            continue

        chunk = metadata[idx]

        print(f"\nResult {rank}")
        print(f"Similarity score: {score:.4f}")
        print(f"Document: {chunk['document_name']}")
        print(f"Page number: {chunk['page_number']}")
        print(f"Chunk ID: {chunk['chunk_id']}")
        print("\nRelevant text:")
        print(chunk["text"])
        print("-" * 60)


if __name__ == "__main__":
    main()
