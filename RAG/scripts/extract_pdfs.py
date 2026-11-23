
import pymupdf
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PDF_DIR = os.path.join(BASE_DIR, "documents")
OUTPUT_DIR = os.path.join(BASE_DIR, "extracted")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_pdf_text(pdf_path):

    doc = pymupdf.open(pdf_path)

    pages = []

    for page_number, page in enumerate(doc, start=1):

        text = page.get_text("text")

        pages.append({
            "page_number": page_number,
            "text": text.strip()
        })

    doc.close()

    return pages


def main():

    for filename in os.listdir(PDF_DIR):

        if filename.lower().endswith(".pdf"):

            pdf_path = os.path.join(PDF_DIR, filename)

            print(f"\nProcessing: {filename}")

            pages = extract_pdf_text(pdf_path)

            output_filename = filename.replace(".pdf", ".json")

            output_path = os.path.join(
                OUTPUT_DIR, output_filename
            )

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(pages, f, indent=4, ensure_ascii=False)

            print(f"Pages extracted: {len(pages)}")
            print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
