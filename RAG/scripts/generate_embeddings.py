
import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer

CHUNKS_DIR = "chunks"
OUTPUT_DIR = "indexes"

os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

def main():

    print("Loading embedding model...")

    model = SentenceTransformer(MODEL_NAME)

    all_chunks = []

    for filename in os.listdir(CHUNKS_DIR):

        if filename.endswith("_chunks.json"):

            path = os.path.join(CHUNKS_DIR, filename)

            with open(path, "r", encoding="utf-8") as f:
                chunks = json.load(f)

            all_chunks.extend(chunks)

    print(f"Total chunks loaded: {len(all_chunks)}")

    texts = [chunk["text"] for chunk in all_chunks]

    print("Generating embeddings...")

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    embeddings = np.asarray(embeddings, dtype="float32")

    output_path = os.path.join(
        OUTPUT_DIR, "aml_embeddings.npy"
    )

    np.save(output_path, embeddings)

    metadata_path = os.path.join(
        OUTPUT_DIR, "aml_chunks_metadata.json"
    )

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(
            all_chunks,
            f,
            indent=4,
            ensure_ascii=False
        )

    print("\nEmbedding generation completed!")
    print("Total vectors:", len(embeddings))
    print("Vector dimensions:", embeddings.shape[1])
    print("Saved:", output_path)
    print("Saved:", metadata_path)


if __name__ == "__main__":
    main()
