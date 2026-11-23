
import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_DIR = Path(__file__).resolve().parent.parent
API_URL = "http://127.0.0.1:8000/search"

TEST_CASES = [
    {
        "typology": "structuring",
        "query": "What are the indicators of structuring transactions below reporting thresholds?",
        "chunk": "RBI_KYC_Master_Direction_p23_structuring_1",
        "source": "RBI_KYC_Master_Direction.pdf",
        "page": 23,
    },
    {
        "typology": "customer_due_diligence",
        "query": "What is customer due diligence?",
        "chunk": "RBI_KYC_Master_Direction_p11_c2",
        "source": "RBI_KYC_Master_Direction.pdf",
        "page": 11,
    },
    {
        "typology": "enhanced_due_diligence",
        "query": "What enhanced due diligence measures should be applied to high-risk customers?",
        "chunk": "FIU_Guidance_p10_c1",
        "source": "FIU_Guidance.pdf",
        "page": 10,
    },
    {
        "typology": "ongoing_monitoring",
        "query": "What transactions should banks monitor as part of ongoing due diligence?",
        "chunk": "RBI_KYC_Master_Direction_p40_c1",
        "source": "RBI_KYC_Master_Direction.pdf",
        "page": 40,
    },
    {
        "typology": "suspicious_transaction_reporting",
        "query": "When should financial institutions report suspicious transactions to the Financial Intelligence Unit?",
        "chunk": "FATF_Recommendations_p20_c2",
        "source": "FATF_Recommendations.pdf",
        "page": 20,
    },
    {
        "typology": "money_mules",
        "query": "How should banks identify and monitor money mule accounts?",
        "chunk": "RBI_KYC_Master_Direction_p64_c1",
        "source": "RBI_KYC_Master_Direction.pdf",
        "page": 64,
    },
]


def evaluate(test):
    payload = {
        "query": test["query"],
        "typology": test["typology"],
        "top_k": 5,
    }

    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=90) as response:
            data = json.load(response)

    except HTTPError as error:
        return {
            "status": "ERROR",
            "reason": f"API returned HTTP {error.code}",
        }

    except (URLError, TimeoutError) as error:
        return {
            "status": "ERROR",
            "reason": f"Connection error: {type(error).__name__}",
        }

    except (ValueError, TypeError):
        return {
            "status": "ERROR",
            "reason": "Invalid API response",
        }

    if not isinstance(data, dict):
        return {"status": "ERROR", "reason": "Unexpected response"}

    guidelines = data.get("retrieved_guidelines", [])
    references = data.get("source_references", [])

    if not isinstance(guidelines, list) or not isinstance(references, list):
        return {"status": "ERROR", "reason": "Invalid response schema"}

    matching = [
        g for g in guidelines
        if isinstance(g, dict)
        and g.get("chunk_id") == test["chunk"]
    ]

    if not matching:
        return {
            "status": "FAIL",
            "reason": "Expected verified chunk not retrieved",
            "returned_chunks": [
                g.get("chunk_id")
                for g in guidelines
                if isinstance(g, dict)
            ],
        }

    hit = matching[0]
    score = hit.get("relevance_score")

    valid = (
        hit.get("source") == test["source"]
        and hit.get("page") == test["page"]
        and hit.get("typology") == test["typology"]
        and bool(hit.get("section"))
        and bool(hit.get("text", "").strip())
        and test["chunk"] in references
        and isinstance(score, (int, float))
        and 0.50 <= score <= 1.0
    )

    return {
        "status": "PASS" if valid else "FAIL",
        "reason": (
            "Expected guidance and metadata verified"
            if valid else "Metadata, citation, or relevance check failed"
        ),
        "chunk_id": hit.get("chunk_id"),
        "relevance_score": score,
    }


print("\n========== AMLens Azure RAG Evaluation ==========")

results = []

for test in TEST_CASES:
    result = evaluate(test)

    results.append({
        "typology": test["typology"],
        "expected_chunk": test["chunk"],
        **result,
    })

    print(
        f"[{result['status']}] "
        f"{test['typology']} - {result['reason']}"
    )

summary = {
    status: sum(r["status"] == status for r in results)
    for status in ("PASS", "FAIL", "ERROR")
}

report = {
    "timestamp": datetime.now().astimezone().isoformat(),
    "total_tests": len(TEST_CASES),
    "summary": summary,
    "results": results,
}

output_dir = BASE_DIR / "reports"
output_dir.mkdir(exist_ok=True)

output_path = output_dir / "azure_rag_evaluation.json"

with open(output_path, "w", encoding="utf-8") as file:
    json.dump(report, file, indent=2, ensure_ascii=False)

print("\n========== Evaluation Summary ==========")
print("Total tests:", len(TEST_CASES))
print("Passed:", summary["PASS"])
print("Failed:", summary["FAIL"])
print("API errors:", summary["ERROR"])
print("Report saved:", output_path)
