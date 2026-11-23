
import os
import json

OUTPUT_DIR = "extracted"

for filename in os.listdir(OUTPUT_DIR):

    if filename.endswith(".json"):

        path = os.path.join(OUTPUT_DIR, filename)

        with open(path, "r", encoding="utf-8") as f:
            pages = json.load(f)

        total_pages = len(pages)
        empty_pages = sum(
            1 for p in pages if not p["text"].strip()
        )

        total_chars = sum(
            len(p["text"]) for p in pages
        )

        print(f"\nDocument: {filename}")
        print(f"Total pages: {total_pages}")
        print(f"Empty pages: {empty_pages}")
        print(f"Pages with text: {total_pages - empty_pages}")
        print(f"Total characters: {total_chars}")

        if pages:
            print("\nSample extracted text:")
            print(pages[0]["text"][:300])
