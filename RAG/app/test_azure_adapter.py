
from app.azure_search_adapter import TeamAzureSearchAdapter


def main():

    print("\n========== AMLens Azure Adapter Test ==========")

    adapter = TeamAzureSearchAdapter()

    result = adapter.search_aml_guidance(
        query=(
            "What are the indicators of structuring "
            "transactions below reporting thresholds?"
        ),
        typology="structuring",
        top_k=5
    )

    print("\nRetrieved guidelines:", len(result.retrieved_guidelines))

    for guideline in result.retrieved_guidelines:

        print("\nChunk ID:", guideline.chunk_id)
        print("Source:", guideline.source)
        print("Section:", guideline.section)
        print("Page:", guideline.page)
        print("Typology:", guideline.typology)

        print(
            "Cosine similarity:",
            round(guideline.relevance_score, 4)
        )

        print("Text:", guideline.text)

    print("\nSource references:", result.source_references)
    print("Relevance notes:", result.relevance_notes)

    print("\nAzure adapter test completed!")


if __name__ == "__main__":
    main()
