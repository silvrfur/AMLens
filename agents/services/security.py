"""No executable tool requests or untrusted free text cross the LLM boundary."""
import hashlib

ALLOWED_TOOLS = frozenset({"backend.read", "rag.search", "llm.generate"})

def mask_account(value: str) -> str:
    return "acct_" + hashlib.sha256(value.encode()).hexdigest()[:16]

def safe_llm_payload(report: dict, allowed_statements: list[str]) -> dict:
    # Full descriptions, alert labels and retrieved passages are intentionally excluded.
    # The LLM selects narrative sentences; deterministic code supplies all facts/citations.
    return {
        "investigation_id": report["investigation_id"],
        "allowed_statements": allowed_statements,
        "allowed_next_steps": report["investigation_narrative"]["recommended_next_steps"],
    }
