
import json
import numpy as np
import faiss
from pathlib import Path

# Project directories
BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE_DIR / "indexes"

# Input files
EMBEDDINGS_PATH = INDEX_DIR / "aml_embeddings.npy"
METADATA_PATH = INDEX_DIR / "aml_chunks_metadata.json"

# Output file
FAISS_INDEX_PATH = INDEX_DIR / "aml_faiss.index"


def main():

    print("Loading embeddings...")

    embeddings = np.load(EMBEDDINGS_PATH)

    print("Loading chunk metadata...")

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # Validate data
    if len(embeddings) != len(metadata):
        raise ValueError("Embedding and metadata counts do not match")

    if not np.isfinite(embeddings).all():
        raise ValueError("Embeddings contain invalid values")

    # FAISS requires float32 vectors
    embeddings = np.asarray(embeddings, dtype="float32")

    vector_count, dimensions = embeddings.shape

    print(f"Total vectors: {vector_count}")
    print(f"Vector dimensions: {dimensions}")

    # Create FAISS index
    index = faiss.IndexFlatIP(dimensions)

    # Add embeddings
    index.add(embeddings)

    # Save index
    faiss.write_index(index, str(FAISS_INDEX_PATH))

    print("\nFAISS index created successfully!")
    print("Vectors indexed:", index.ntotal)
    print("Index dimensions:", index.d)
    print("Saved at:", FAISS_INDEX_PATH)


if __name__ == "__main__":
    main()
