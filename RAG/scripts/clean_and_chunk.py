
import os
import json
import re

INPUT_DIR = "extracted"
OUTPUT_DIR = "chunks"

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_text(text):

    # Remove unnecessary spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def create_chunks(text):

    chunks = []
    start = 0
    length = len(text)

    while start < length:

        end = min(start + CHUNK_SIZE, length)

        # Try to end at a paragraph or sentence boundary
        if end < length:
            boundary = max(
                text.rfind("\n", start + 800, end),
                text.rfind(". ", start + 800, end)
            )

            if boundary > start:
                end = boundary + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        start = max(start + 1, end - CHUNK_OVERLAP)

    return chunks


def main():

    for filename in os.listdir(INPUT_DIR):

        if not filename.endswith(".json"):
            continue

        input_path = os.path.join(INPUT_DIR, filename)

        with open(input_path, "r", encoding="utf-8") as f:
            pages = json.load(f)

        document_id = os.path.splitext(filename)[0]

        all_chunks = []

        for page in pages:

            page_number = page["page_number"]

            text = clean_text(page["text"])

            page_chunks = create_chunks(text)

            for index, chunk in enumerate(page_chunks, start=1):

                all_chunks.append({
                    "chunk_id": (
                        f"{document_id}_p{page_number}_c{index}"
                    ),
                    "document_id": document_id,
                    "document_name": filename.replace(".json", ".pdf"),
                    "page_number": page_number,
                    "chunk_index": index,
                    "text": chunk,
                    "char_count": len(chunk)
                })

        output_filename = filename.replace(".json", "_chunks.json")

        output_path = os.path.join(
            OUTPUT_DIR, output_filename
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                all_chunks,
                f,
                indent=4,
                ensure_ascii=False
            )

        print(f"\nDocument: {filename}")
        print(f"Total chunks: {len(all_chunks)}")
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
