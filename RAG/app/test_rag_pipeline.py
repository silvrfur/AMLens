
from app.rag_pipeline import AMLRAGPipeline


def main():

    pipeline = AMLRAGPipeline()

    question = input("\nAsk AMLens a question: ")

    response = pipeline.run(question)

    print("\n========== AMLENS RAG PIPELINE ==========")

    print("Status:", response["status"])

    print("\nQuestion:")
    print(response["question"])

    print("\nRetrieved Sources:")

    for i, source in enumerate(response["sources"], start=1):

        print(f"\nSource {i}")
        print("Document:", source["document_name"])
        print("Page:", source["page_number"])
        print("Similarity:", round(source["similarity_score"], 4))

    if response["prompt"]:
        print("\nRAG prompt prepared successfully!")
        print("Prompt length:", len(response["prompt"]), "characters")

    print("\nAzure OpenAI integration: Pending Azure access")


if __name__ == "__main__":
    main()
