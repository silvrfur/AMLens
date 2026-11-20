
import json
import re
from pathlib import Path

import pymupdf

BASE_DIR = Path(__file__).resolve().parent.parent

PDF_PATH = (
    BASE_DIR / "documents" / "RBI_KYC_Master_Direction.pdf"
)

CHUNKS_PATH = (
    BASE_DIR / "chunks" / "RBI_KYC_Master_Direction_chunks.json"
)

NEW_CHUNK_ID = "RBI_KYC_Master_Direction_p23_structuring_1"

# Read the original PDF page
with pymupdf.open(PDF_PATH) as doc:
    page_text = doc[22].get_text()

# Extract the complete paragraph 21(6)
match = re.search(
    r"\(6\)\s*When the bank has reason to believe.*?(?=\s*\(7\))",
    page_text,
    re.DOTALL | re.IGNORECASE
)

if not match:
    raise ValueError("Could not locate RBI paragraph 21(6)")

passage = match.group(0).strip()

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)

# Reuse authentic document metadata
original = next(
    chunk for chunk in chunks
    if chunk["chunk_id"] == "RBI_KYC_Master_Direction_p23_c2"
)

existing = next(
    (chunk for chunk in chunks
     if chunk["chunk_id"] == NEW_CHUNK_ID),
    None
)

if existing is None:
    next_index = max(
        chunk["chunk_index"]
        for chunk in chunks
        if chunk["page_number"] == 23
    ) + 1

    new_chunk = {
        "chunk_id": NEW_CHUNK_ID,
        "document_id": original["document_id"],
        "document_name": original["document_name"],
        "page_number": 23,
        "chunk_index": next_index,
        "text": passage,
        "char_count": len(passage)
    }

    chunks.append(new_chunk)
else:
    existing["text"] = passage
    existing["char_count"] = len(passage)

with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

print("Verified structuring passage added successfully!")
print("Chunk ID:", NEW_CHUNK_ID)
print("Passage:\n", passage)
print("Total RBI chunks:", len(chunks))
