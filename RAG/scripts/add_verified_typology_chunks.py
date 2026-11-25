"""Add human-reviewed, complete regulatory passages for agent typologies.

Same approach as add_verified_structuring_chunk.py: each passage is extracted
verbatim from the original PDF page (whole paragraphs, no rewriting) and
stored as its own chunk with a stable ID. Each chunk gets exactly one typology
in app/typology_annotations.py, because Azure stores a single `typology`
string and the retrieval agent drops chunks whose typology differs.

Reviewed and approved 2026-11-24:
- unusual_activity: RBI KYC 39-40(1), FIU 4.10.1, FATF INR.10 para 20
- rapid_movement:   RBI KYC para 40 (incl. (3) high turnover, (4) third-party
                    deposits followed by large cash withdrawals)
- fan_in_out:       RBI KYC 41(2) Explanation (many deposits into one
                    account / many cheques of similar amounts)
Considered and rejected: RBI KYC para 68 (money mules) for rapid_movement.

Run from the RAG folder, then regenerate embeddings and the FAISS index:
    python scripts/add_verified_typology_chunks.py
    python scripts/generate_embeddings.py
    python scripts/build_faiss_index.py
"""
import json
import re
from pathlib import Path

import pymupdf

BASE_DIR = Path(__file__).resolve().parent.parent

PASSAGES = [
    {
        "chunk_id": "RBI_KYC_Master_Direction_p40_unusual_activity_1",
        "document": "RBI_KYC_Master_Direction",
        "page": 40,
        "pattern": r"39\. The bank shall undertake ongoing due diligence.*?legitimate purpose\.",
    },
    {
        "chunk_id": "RBI_KYC_Master_Direction_p40_rapid_movement_1",
        "document": "RBI_KYC_Master_Direction",
        "page": 40,
        "pattern": r"40\. Without prejudice to the generality.*?cash withdrawals for large amounts\.",
    },
    {
        "chunk_id": "RBI_KYC_Master_Direction_p41_fan_in_out_1",
        "document": "RBI_KYC_Master_Direction",
        "page": 41,
        "pattern": r"Explanation: Cases where a large number of cheque books.*?FIU-IND\.",
    },
    {
        "chunk_id": "FIU_Guidance_p10_unusual_activity_1",
        "document": "FIU_Guidance",
        "page": 10,
        "pattern": r"4\.10\.1 Relevant persons.*?appear unusual or suspicious\.",
    },
    {
        "chunk_id": "FATF_Recommendations_p73_unusual_activity_1",
        "document": "FATF_Recommendations",
        "page": 73,
        "pattern": r"20\.\s*Financial institutions should examine, as far as reasonably possible.*?appear unusual or suspicious\.",
    },
]


def extract(document: str, page: int, pattern: str) -> str:
    with pymupdf.open(BASE_DIR / "documents" / f"{document}.pdf") as doc:
        page_text = doc[page - 1].get_text()
    matches = list(re.finditer(pattern, page_text, re.DOTALL))
    if len(matches) != 1:
        raise ValueError(f"{document} p{page}: expected 1 match, found {len(matches)}")
    return matches[0].group(0).strip()


def main():
    for spec in PASSAGES:
        passage = extract(spec["document"], spec["page"], spec["pattern"])
        chunks_path = BASE_DIR / "chunks" / f"{spec['document']}_chunks.json"
        raw = chunks_path.read_text(encoding="utf-8")
        chunks = json.loads(raw)
        # Keep the file's existing indentation so the diff shows only real changes.
        second_line = raw.splitlines()[1]
        indent = len(second_line) - len(second_line.lstrip(" "))

        # Reuse authentic document metadata from an existing chunk of the same page.
        original = next(c for c in chunks if c["page_number"] == spec["page"])
        existing = next((c for c in chunks if c["chunk_id"] == spec["chunk_id"]), None)

        if existing is None:
            chunks.append({
                "chunk_id": spec["chunk_id"],
                "document_id": original["document_id"],
                "document_name": original["document_name"],
                "page_number": spec["page"],
                "chunk_index": max(c["chunk_index"] for c in chunks
                                   if c["page_number"] == spec["page"]) + 1,
                "text": passage,
                "char_count": len(passage),
            })
        else:
            existing["text"] = passage
            existing["char_count"] = len(passage)

        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=indent)

        print(f"\n{spec['chunk_id']} ({len(passage)} chars)\n{passage}")


if __name__ == "__main__":
    main()
