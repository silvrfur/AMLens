
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.typology_annotations import VERIFIED_CHUNKS

load_dotenv(BASE_DIR / ".env", override=True)

METADATA_PATH = (
    BASE_DIR / "indexes" / "aml_chunks_metadata.json"
)

# Confirm each annotation points to the intended passage.
REQUIRED_PHRASES = {
    "structuring": "intentionally structuring",
    "customer_due_diligence": "Customer Due Diligence (CDD)",
    "enhanced_due_diligence": "Enhanced Due Diligence (EDD) Norms",
    "ongoing_monitoring": "On-going Due Diligence",
    "suspicious_transaction_reporting": (
        "Reporting of suspicious transactions"
    ),
    "money_mules": "Money Mules",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write verified metadata updates to Azure"
    )
    args = parser.parse_args()

    with open(METADATA_PATH, encoding="utf-8") as file:
        chunks = json.load(file)

    lookup = {
        item["chunk_id"]: item
        for item in chunks
    }

    if len(lookup) != len(chunks):
        raise ValueError("Duplicate local chunk IDs detected")

    client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
        credential=AzureKeyCredential(
            os.environ["AZURE_SEARCH_ADMIN_KEY"]
        )
    )

    initial_count = client.get_document_count()
    updates = []
    seen_ids = set()

    print("\n===== AMLens Typology Metadata Update =====")
    print("Indexed documents:", initial_count)

    for typology, annotations in VERIFIED_CHUNKS.items():
        for chunk_id, info in annotations.items():

            if chunk_id in seen_ids:
                raise ValueError(
                    f"Chunk assigned multiple categories: {chunk_id}"
                )

            seen_ids.add(chunk_id)

            if chunk_id not in lookup:
                raise ValueError(
                    f"Local chunk not found: {chunk_id}"
                )

            local = lookup[chunk_id]
            remote = client.get_document(key=chunk_id)

            # Check that we are updating the correct passage.
            for local_field, remote_field in [
                ("chunk_id", "chunk_id"),
                ("document_name", "source"),
                ("page_number", "page"),
                ("text", "text"),
            ]:
                if local[local_field] != remote[remote_field]:
                    raise ValueError(
                        f"Source mismatch for {chunk_id}: "
                        f"{remote_field}"
                    )

            required = REQUIRED_PHRASES.get(typology)

            if required is None or (
                required.lower() not in local["text"].lower()
            ):
                raise ValueError(
                    f"Review annotation for {chunk_id}: "
                    "expected passage phrase not found"
                )

            section = info["section"].strip()

            if not section:
                raise ValueError(
                    f"Missing verified section for {chunk_id}"
                )

            updates.append({
                "chunk_id": chunk_id,
                "section": section,
                "typology": typology
            })

            print(f"\nChunk: {chunk_id}")
            print("Category:", typology)
            print("Section:", section)

    print("\nVerified annotations:", len(updates))

    if not args.apply:
        print("\nDRY RUN: No Azure metadata was changed.")
        return

    results = client.merge_documents(documents=updates)

    failures = [
        item.key for item in results
        if not item.succeeded
    ]

    if failures:
        raise RuntimeError(
            f"Metadata update failed for: {failures}"
        )

    print("\nMetadata updates submitted successfully!")
    print("Updated chunks:", len(results))
    print("Indexed document count:", client.get_document_count())
    print("Existing embeddings were not regenerated.")


if __name__ == "__main__":
    main()
