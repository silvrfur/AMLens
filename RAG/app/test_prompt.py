
from app.retriever import AMLRetriever
from app.prompt_template import SYSTEM_PROMPT, build_rag_prompt


def main():

    retriever = AMLRetriever()

    question = input("\nEnter your AML question: ")

    results = retriever.retrieve(question, top_k=5)

    prompt = build_rag_prompt(question, results)

    print("\n========== SYSTEM PROMPT ==========")
    print(SYSTEM_PROMPT)

    print("\n========== GENERATED RAG PROMPT ==========")
    print(prompt)


if __name__ == "__main__":
    main()
