
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.typology_annotations import VERIFIED_CHUNKS

load_dotenv(BASE_DIR / ".env", override=True)

METADATA_FILE = (
    BASE_DIR / "indexes" / "aml_chunks_metadata.json"
)

VECTOR_DIMENSIONS = 1536
BATCH_SIZE = 8


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of chunks; use 0 for all approved chunks"
    )

    parser.add_argument(
        "--upload",
        action="store_true",
        help="Actually generate embeddings and upload"
    )

    args = parser.parse_args()

    if args.limit < 0:
        raise ValueError("Limit cannot be negative")

    # Load existing AML chunks
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print("Total local chunks:", len(chunks))

    approved = {
        name.strip()
        for name in os.getenv(
            "APPROVED_AML_DOCUMENTS", ""
        ).split(",")
        if name.strip()
    }

    if not approved:
        raise ValueError(
            "Set APPROVED_AML_DOCUMENTS in .env first"
        )

    available = {
        c["document_name"] for c in chunks
    }

    if not approved.issubset(available):
        raise ValueError(
            f"Unknown document names: {approved - available}"
        )

    # Use only approved documents
    selected = [
        c for c in chunks
        if c["document_name"] in approved
        and c["text"].strip()
    ]

    # Preserve manually verified typology annotations
    annotations = {}

    for typology, items in VERIFIED_CHUNKS.items():
        for chunk_id, info in items.items():
            annotations[chunk_id] = {
                "section": info["section"],
                "typology": typology
            }

    # Prioritize verified chunks for the first smoke test
    selected.sort(
        key=lambda c: c["chunk_id"] not in annotations
    )

    if args.limit:
        selected = selected[:args.limit]

    ids = [c["chunk_id"] for c in selected]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate chunk IDs detected")

    print("Selected chunks:", len(selected))

    for item in selected[:5]:
        print(" -", item["chunk_id"])

    if not args.upload:
        print("\nDry run only. Nothing uploaded.")
        return

    # Azure connections
    credential = AzureKeyCredential(
        os.environ["AZURE_SEARCH_ADMIN_KEY"]
    )

    index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]

    index_client = SearchIndexClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        credential=credential
    )

    index = index_client.get_index(index_name)

    vector_field = next(
        f for f in index.fields
        if f.name == "content_vector"
    )

    if vector_field.vector_search_dimensions != VECTOR_DIMENSIONS:
        raise ValueError("Azure index vector dimensions mismatch")

    search_client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=index_name,
        credential=credential
    )

    openai_client = OpenAI(
        base_url=os.environ["AZURE_OPENAI_BASE_URL"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        timeout=60.0,
        max_retries=2
    )

    uploaded = 0

    for start in range(0, len(selected), BATCH_SIZE):

        batch = selected[start:start + BATCH_SIZE]

        texts = [c["text"] for c in batch]

        response = openai_client.embeddings.create(
            model=os.environ[
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
            ],
            input=texts,
            encoding_format="float"
        )

        vectors = {
            item.index: item.embedding
            for item in response.data
        }

        documents = []

        for i, chunk in enumerate(batch):

            vector = vectors[i]

            if len(vector) != VECTOR_DIMENSIONS:
                raise ValueError("Embedding dimensions mismatch")

            annotation = annotations.get(
                chunk["chunk_id"], {}
            )

            documents.append({
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "source": chunk["document_name"],
                "document_id": chunk["document_id"],
                "section": annotation.get("section", ""),
                "page": chunk.get("page_number"),
                "typology": annotation.get("typology", ""),
                "content_vector": vector
            })

        results = search_client.upload_documents(
            documents=documents
        )

        failures = [
            r.key for r in results
            if not r.succeeded
        ]

        if failures:
            raise RuntimeError(
                f"Azure Search rejected chunks: {failures}"
            )

        uploaded += len(results)

        print(
            f"Uploaded {uploaded}/{len(selected)} chunks"
        )

    print("\nAzure upload completed!")
    print("Total uploaded:", uploaded)
    print("Index:", index_name)


if __name__ == "__main__":
    main()
