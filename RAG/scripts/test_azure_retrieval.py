
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)


def main():

    print("\n========== AMLens Azure Retrieval Test ==========")

    search_client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
        credential=AzureKeyCredential(
            os.environ["AZURE_SEARCH_ADMIN_KEY"]
        )
    )

    # Step 1: Verify index count
    print("\n1. Verifying Azure Search index...")

    count = search_client.get_document_count()

    print("Index:", os.environ["AZURE_SEARCH_INDEX_NAME"])
    print("Total indexed chunks:", count)

    # Step 2: Verify original citation metadata
    print("\n2. Checking verified structuring passage...")

    chunk_id = "RBI_KYC_Master_Direction_p23_structuring_1"

    document = search_client.get_document(key=chunk_id)

    print("Chunk ID:", document["chunk_id"])
    print("Source:", document["source"])
    print("Section:", document["section"])
    print("Page:", document["page"])
    print("Typology:", document["typology"])
    print("Passage:", document["text"])

    # Step 3: Generate Azure OpenAI query embedding
    print("\n3. Generating query embedding...")

    question = (
        "What are the indicators of structuring "
        "transactions below reporting thresholds?"
    )

    openai_client = OpenAI(
        base_url=os.environ["AZURE_OPENAI_BASE_URL"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        timeout=60.0,
        max_retries=0
    )

    response = openai_client.embeddings.create(
        model=os.environ[
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        ],
        input=question
    )

    query_vector = response.data[0].embedding

    print("Question:", question)
    print("Embedding dimensions:", len(query_vector))

    if len(query_vector) != 1536:
        raise ValueError("Unexpected embedding dimensions")

    # Step 4: Perform one Azure vector search
    print("\n4. Searching Azure AI Search...")

    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=5,
        fields="content_vector",
        kind="vector"
    )

    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=[
            "chunk_id",
            "text",
            "source",
            "section",
            "page",
            "typology"
        ],
        top=5
    )

    for i, result in enumerate(results, start=1):

        raw_score = result["@search.score"]

        # Conversion for cosine-only vector searches.
        cosine_similarity = 2.0 - (1.0 / raw_score)

        print(f"\n----- Result {i} -----")
        print("Chunk ID:", result["chunk_id"])
        print("Source:", result["source"])
        print("Page:", result.get("page"))
        print("Section:", result.get("section"))
        print("Typology:", result.get("typology"))
        print("Azure score:", round(raw_score, 4))
        print(
            "Cosine similarity:",
            round(cosine_similarity, 4)
        )
        print("Text:", result["text"][:350])

    print("\nAzure retrieval test completed!")


if __name__ == "__main__":
    main()
