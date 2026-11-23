
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
METADATA_PATH = BASE_DIR / "indexes" / "aml_chunks_metadata.json"

with open(METADATA_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)

keywords = [
    r"\bstructuring\b",
    r"\bsmurfing\b",
    r"multiple small transactions",
    r"multiple small deposits",
    r"avoid(?:ing)? reporting thresholds",
    r"split(?:ting)? transactions",
    r"split(?:ting)? deposits"
]

print("\n========== TYPOLOGY COVERAGE CHECK ==========")
print("Total chunks:", len(chunks))

matches = []

for chunk in chunks:
    text = chunk["text"]

    if any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in keywords
    ):
        matches.append(chunk)

print("Matching chunks:", len(matches))

for chunk in matches[:15]:
    print("\n-----------------------------------")
    print("Chunk ID:", chunk["chunk_id"])
    print("Document:", chunk["document_name"])
    print("Page:", chunk["page_number"])
    print(
        "Text:",
        re.sub(r"\s+", " ", chunk["text"])[:500]
    )
