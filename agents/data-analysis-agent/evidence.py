"""
evidence.py -- Step 6 of the Data-Analysis Agent

Job of this file: take a hypothesis + its Analyst result + its Verifier
verdict, and package them into a fixed-shape Evidence record.

The key design choice: Evidence is a FROZEN dataclass with a fixed set
of fields. This isn't just a convention we promise to follow -- Python
itself will raise an error if any code, anywhere, ever tries to attach
an extra field (like a business recommendation) to an Evidence object
after it's created. Same principle as summarize_evidence() in Project 3:
the schema does the enforcing, not our discipline.
"""

import json
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Evidence:
    hypothesis: str
    method: str
    result: object       # whatever the Analyst computed (number, dict, etc.)
    confidence: str       # "high" | "moderate" | "low"
    verdict: str          # "verified" | "rejected" -- about trust, not action
    reason: str           # why the Verifier reached that verdict

    def to_dict(self) -> dict:
        return asdict(self)


def _determine_confidence(verifier_result: dict) -> str:
    """Confidence reflects how strongly the Verifier's own process backs
    this result -- not how "interesting" the finding is."""
    if verifier_result["verdict"] == "rejected":
        return "low"
    if "did not report a p_value" in verifier_result["reason"]:
        # Analyst didn't follow the schema -- genuinely unverified,
        # lower trust than a deliberate descriptive result.
        return "low"
    if "Descriptive" in verifier_result["reason"]:
        # Verified because there was nothing to statistically dispute,
        # not because it survived a real replication check.
        return "moderate"
    return "high"


def build_evidence(hypothesis: str, analyst_result: dict, verifier_result: dict) -> Evidence:
    """Combines the outputs of the Analyst and Verifier into one fixed
    Evidence record. Note what's deliberately absent: nothing here ever
    says what to DO about the finding -- that stays out of scope by
    construction, not by convention."""
    if analyst_result.get("success"):
        method = analyst_result.get("result", {}).get("summary", "unspecified method")
        result_value = analyst_result.get("result")
    else:
        method = "execution failed"
        result_value = analyst_result.get("error")

    return Evidence(
        hypothesis=hypothesis,
        method=method,
        result=result_value,
        confidence=_determine_confidence(verifier_result),
        verdict=verifier_result["verdict"],
        reason=verifier_result["reason"],
    )


if __name__ == "__main__":
    # Standalone test: build Evidence from KNOWN results (no LLM, no
    # sandbox needed here -- this file only assembles what's already
    # been computed) and prove the frozen schema actually blocks an
    # attempt to sneak in an extra field.
    analyst_result = {
        "success": True,
        "result": {"summary": "ANOVA units_sold by region", "value": 0.2626, "p_value": 0.2626},
    }
    verifier_result = {
        "verdict": "verified",
        "reason": "Conclusion (significant=False) held consistently across both random data splits.",
    }

    evidence = build_evidence(
        "Is there a significant difference in average units sold across regions?",
        analyst_result,
        verifier_result,
    )
    print("Evidence built:")
    print(json.dumps(evidence.to_dict(), indent=2))

    print("\nTrying to attach a business recommendation to it...")
    try:
        evidence.recommendation = "You should focus marketing on the East region."
        print("PROBLEM: that should not have been allowed.")
    except Exception as e:
        print(f"Blocked as expected -- {type(e).__name__}: {e}")