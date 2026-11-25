
from app.retriever import AMLRetriever
from app.prompt_template import SYSTEM_PROMPT, build_rag_prompt


class AMLRAGPipeline:

    def __init__(self):

        print("Initializing AMLens RAG Pipeline...")

        self.retriever = AMLRetriever()

        print("RAG Pipeline initialized successfully!")

    def run(self, question, top_k=5):

        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        # Step 1: Retrieve relevant AML documents
        retrieved_chunks = self.retriever.retrieve(
            question,
            top_k=top_k
        )

        if not retrieved_chunks:
            return {
                "question": question,
                "sources": [],
                "system_prompt": SYSTEM_PROMPT,
                "prompt": None,
                "status": "no_relevant_context"
            }

        # Step 2: Prepare the RAG prompt
        prompt = build_rag_prompt(
            question,
            retrieved_chunks
        )

        # Step 3: Return prepared data
        # Azure OpenAI will be connected here later

        return {
            "question": question,
            "sources": retrieved_chunks,
            "system_prompt": SYSTEM_PROMPT,
            "prompt": prompt,
            "status": "context_retrieved"
        }
