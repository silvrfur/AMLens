
import os
from pathlib import Path

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient

from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    HnswParameters,
    VectorSearchProfile,
)


# ==========================================
# 1. Load environment variables
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=True)

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
SEARCH_KEY = os.environ["AZURE_SEARCH_ADMIN_KEY"]
INDEX_NAME = os.environ["AZURE_SEARCH_INDEX_NAME"]

VECTOR_DIMENSIONS = 1536


# ==========================================
# 2. Connect to Azure AI Search
# ==========================================

client = SearchIndexClient(
    endpoint=SEARCH_ENDPOINT,
    credential=AzureKeyCredential(SEARCH_KEY),
)


# ==========================================
# 3. Define index fields
# ==========================================

fields = [

    SimpleField(
        name="chunk_id",
        type=SearchFieldDataType.String,
        key=True,
        filterable=True,
    ),

    SearchableField(
        name="text",
        type=SearchFieldDataType.String,
    ),

    SearchableField(
        name="source",
        type=SearchFieldDataType.String,
        filterable=True,
    ),

    SimpleField(
        name="document_id",
        type=SearchFieldDataType.String,
        filterable=True,
    ),

    SearchableField(
        name="section",
        type=SearchFieldDataType.String,
        filterable=True,
    ),

    SimpleField(
        name="page",
        type=SearchFieldDataType.Int32,
        filterable=True,
    ),

    SearchableField(
        name="typology",
        type=SearchFieldDataType.String,
        filterable=True,
    ),

    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(
            SearchFieldDataType.Single
        ),
        searchable=True,
        vector_search_dimensions=VECTOR_DIMENSIONS,
        vector_search_profile_name="amlens-vector-profile",
    ),
]


# ==========================================
# 4. Configure vector search
# ==========================================

vector_search = VectorSearch(

    algorithms=[
        HnswAlgorithmConfiguration(
            name="amlens-hnsw",
            parameters=HnswParameters(
                metric="cosine"
            ),
        )
    ],

    profiles=[
        VectorSearchProfile(
            name="amlens-vector-profile",
            algorithm_configuration_name="amlens-hnsw",
        )
    ],
)


# ==========================================
# 5. Create the index
# ==========================================

def main():

    print("\n===== AMLens Azure Search Index =====")

    existing_indexes = list(client.list_index_names())

    if INDEX_NAME in existing_indexes:

        print("Index already exists:", INDEX_NAME)

        existing = client.get_index(INDEX_NAME)

        vector_field = next(
            (
                field for field in existing.fields
                if field.name == "content_vector"
            ),
            None
        )

        if (
            vector_field is None
            or vector_field.vector_search_dimensions
            != VECTOR_DIMENSIONS
        ):
            raise RuntimeError(
                "Existing index has missing or incompatible "
                "vector dimensions. Do not overwrite it."
            )

        required_fields = {
            field.name for field in fields
        }

        actual_fields = {
            field.name for field in existing.fields
        }

        missing = required_fields - actual_fields

        if missing:
            raise RuntimeError(
                f"Existing index is missing fields: {missing}"
            )

        print("Existing index structure verified.")
        return

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
    )

    result = client.create_index(index)

    print("Azure AI Search index created successfully!")
    print("Index name:", result.name)
    print("Vector dimensions:", VECTOR_DIMENSIONS)
    print("Vector algorithm: HNSW")
    print("Similarity metric: cosine")
    print("Total fields:", len(result.fields))


if __name__ == "__main__":
    main()
