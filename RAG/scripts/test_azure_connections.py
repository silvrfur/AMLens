
import os
from pathlib import Path

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parent.parent

# Load Azure credentials from .env
load_dotenv(BASE_DIR / ".env", override=True)

def test_azure_search():

    print("\n1. Connecting to Azure AI Search...")

    client = SearchIndexClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        credential=AzureKeyCredential(
            os.environ["AZURE_SEARCH_ADMIN_KEY"]
        )
    )

    indexes = list(client.list_index_names())

    print("Azure AI Search connected successfully!")
    print("Available indexes:", indexes)


def test_azure_openai():

    print("\n2. Connecting to Azure OpenAI...")

    client = OpenAI(
        base_url=os.environ["AZURE_OPENAI_BASE_URL"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        timeout=30.0,
        max_retries=0
    )

    response = client.embeddings.create(
        model=os.environ[
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        ],
        input="What is customer due diligence?"
    )

    embedding = response.data[0].embedding

    print("Azure OpenAI connected successfully!")
    print("Embedding dimensions:", len(embedding))


if __name__ == "__main__":

    print("========== AMLens Azure Test ==========")

    test_azure_search()
    test_azure_openai()

    print("\nAll Azure connections successful!")
