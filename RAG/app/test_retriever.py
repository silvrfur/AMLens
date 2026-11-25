
from app.retriever import AMLRetriever

def main():

    retriever = AMLRetriever()

    question = input("\nEnter your AML question: ")

    results = retriever.retrieve(question, top_k=5)

    print("\n========== RETRIEVED CONTEXT ==========")

    for i, result in enumerate(results, start=1):

        print(f"\nResult {i}")
        print("Document:", result["document_name"])
        print("Page:", result["page_number"])
        print("Similarity:", round(result["similarity_score"], 4))
        print("Text:", result["text"])
        print("-" * 60)


if __name__ == "__main__":
    main()
