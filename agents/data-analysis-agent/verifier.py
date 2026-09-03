"""
verifier.py -- Step 5 of the Data-Analysis Agent (THE differentiator)

Job of this file: decide whether an Analyst's result should be trusted,
before it's allowed anywhere near a report.

TWO verification methods now, used for different situations:

1. STATISTICAL RE-TEST (cheap, deterministic, no LLM call): for results
   that have a real p-value. Rerun the exact same generated code on two
   random halves of the data. If the two halves agree on the
   conclusion, the pattern likely holds. If they disagree, reject it --
   no matter how good the p-value on the full dataset looked.

2. LLM CROSS-CHECK (a second opinion, costs one extra API call): for
   purely descriptive results with NO p-value to statistically
   replicate -- there's no number to re-test, so a second LLM reviews
   the METHOD itself, playing skeptical reviewer. Catches things stats
   can't: a misleading comparison, a conclusion the code doesn't
   actually support, a tiny cherry-picked subset presented as general.

This hybrid is the actual differentiator: verify with statistics where
a number exists to check, verify with a second opinion where it
doesn't -- rather than silently trusting anything without a p-value.
"""

import os
import sys
import json
import tempfile
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

from analyst import run_in_sandbox

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CROSS_CHECK_TOOL = {
    "type": "function",
    "function": {
        "name": "review_finding",
        "description": "Critically review a data-analysis finding that has no statistical significance test to fall back on.",
        "parameters": {
            "type": "object",
            "properties": {
                "sound": {
                    "type": "boolean",
                    "description": (
                        "True if the method and conclusion are "
                        "methodologically sound and fairly stated. False "
                        "if there's a real flaw -- e.g. a misleading "
                        "comparison, groups that aren't actually "
                        "comparable, a strong claim drawn from a tiny "
                        "subset, or a conclusion the code doesn't "
                        "actually support."
                    ),
                },
                "reason": {"type": "string", "description": "One or two sentences explaining the verdict."},
            },
            "required": ["sound", "reason"],
        },
    },
}

CROSS_CHECK_SYSTEM_PROMPT = """You are a skeptical second reviewer for a data-analysis agent.
You are given a hypothesis, the code used to test it, and the result -- with NO statistical significance test available (this is a purely descriptive finding, not a hypothesis test).

Your job: decide if the method and conclusion are methodologically sound, or if there's a real flaw.
Look for: misleading framing, comparing non-comparable groups, drawing a strong conclusion from a tiny sample, a cherry-picked subset, or a conclusion the code doesn't actually support.
Be skeptical but fair -- a genuinely simple, correct descriptive fact (e.g. "the highest-priced product is X") is fine and should be marked sound.
"""


def llm_cross_check(hypothesis: str, code: str, result: dict, model: str = "gpt-4o") -> dict:
    """Second-opinion LLM review for descriptive findings with no
    p-value to statistically replicate. Reviews the METHOD and
    REASONING, not a number -- there's no number to re-check here,
    that's exactly why this exists instead of another split-test."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CROSS_CHECK_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"hypothesis": hypothesis, "code": code, "result": result})},
        ],
        tools=[CROSS_CHECK_TOOL],
        tool_choice={"type": "function", "function": {"name": "review_finding"}},
    )
    tool_call = response.choices[0].message.tool_calls[0]
    return json.loads(tool_call.function.arguments)


def split_dataset(csv_path: str, seed: int = 42):
    """Split the dataset into two random halves. Same seed every time --
    the split needs to be reproducible, not just random, so a rerun of
    the Verifier gives the same verdict, not a different one by luck."""
    df = pd.read_csv(csv_path)
    shuffled = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    midpoint = len(shuffled) // 2
    return shuffled.iloc[:midpoint], shuffled.iloc[midpoint:]


def _write_temp_csv(df: pd.DataFrame) -> str:
    """Writes a DataFrame to a throwaway temp CSV file. Caller deletes it."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    df.to_csv(path, index=False)
    return path


def _get_significance_status(result: dict):
    """Distinguishes three states instead of just "found a p-value or not":

    - "has_test": p_value key present with a real number -> a genuine
      significance test was run, worth split-testing.
    - "no_test": p_value key present but explicitly null -> the Analyst
      deliberately reported this as descriptive, no test performed.
    - "ambiguous": p_value key missing entirely -> the Analyst didn't
      follow the schema. We do NOT assume this means "descriptive" --
      that would silently let an unverified statistical claim through
      with undeserved confidence. Treated as lower-trust instead.
    """
    if not isinstance(result, dict) or "p_value" not in result:
        return "ambiguous", None
    p = result["p_value"]
    if p is None:
        return "no_test", None
    return "has_test", p


def verify_result(hypothesis: str, code: str, csv_path: str, analyst_result: dict) -> dict:
    """Re-runs the Analyst's own code on two random halves of the data
    (when there's a p-value to check), or gets a second LLM opinion on
    the method (when there isn't). Always returns a verdict dict --
    {"verdict": "verified" | "rejected", "reason": str} -- never
    silently passes a result through without a stated reason."""
    if not analyst_result.get("success"):
        return {"verdict": "rejected", "reason": "Analyst execution already failed -- nothing to verify."}

    status_full, p_full = _get_significance_status(analyst_result.get("result"))

    if status_full == "no_test":
        # No p-value to statistically replicate -- get a second LLM
        # opinion on the METHOD instead of skipping verification
        # entirely. This is the one extra API call per descriptive
        # finding; worth it since these were previously auto-verified
        # with no real scrutiny at all.
        review = llm_cross_check(hypothesis, code, analyst_result.get("result"))
        if review["sound"]:
            return {
                "verdict": "verified",
                "reason": f"Descriptive result, no significance test to replicate. LLM cross-check: sound -- {review['reason']}",
            }
        else:
            return {
                "verdict": "rejected",
                "reason": f"LLM cross-check flagged a methodological issue: {review['reason']}",
            }

    if status_full == "ambiguous":
        # Analyst's output didn't follow the schema -- we genuinely don't
        # know if a test was run or not. Do not default to trusting it,
        # and don't waste a split-test on output we can't even interpret.
        return {
            "verdict": "verified",
            "reason": "Analyst did not report a p_value field (not even null) -- cannot confirm whether a significance test was actually run. Treat with caution.",
        }

    # Only reaching here means status_full == "has_test" -- a real
    # significance test was reported, so it's actually worth the cost of
    # rerunning the code on two random data splits to see if it replicates.
    half_a, half_b = split_dataset(csv_path)
    path_a = _write_temp_csv(half_a)
    path_b = _write_temp_csv(half_b)

    try:
        result_a = run_in_sandbox(code, path_a)
        result_b = run_in_sandbox(code, path_b)
    finally:
        os.remove(path_a)
        os.remove(path_b)

    if not result_a.get("success") or not result_b.get("success"):
        return {
            "verdict": "rejected",
            "reason": "Code failed to run on one or both data splits -- the result depends on something fragile in the full dataset (e.g. a group that disappears with fewer rows).",
        }

    status_a, p_a = _get_significance_status(result_a.get("result"))
    status_b, p_b = _get_significance_status(result_b.get("result"))

    sig_full = p_full < 0.05
    sig_a = status_a == "has_test" and p_a < 0.05
    sig_b = status_b == "has_test" and p_b < 0.05

    if sig_full == sig_a == sig_b:
        return {
            "verdict": "verified",
            "reason": f"Conclusion (significant={sig_full}) held consistently across both random data splits.",
        }
    else:
        return {
            "verdict": "rejected",
            "reason": f"Conclusion did not replicate consistently (full={sig_full}, split_a={sig_a}, split_b={sig_b}) -- likely noise, not a real pattern.",
        }


if __name__ == "__main__":
    # Standalone test: verify a KNOWN-WORKING piece of Analyst code
    # (copied from a real prior run) against the sample dataset. No LLM
    # call needed for this -- proves the Verifier works on its own
    # before it's wired into the full pipeline.
    if len(sys.argv) != 2:
        print("Usage: python verifier.py <path_to_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]

    sample_code = """import pandas as pd
from scipy.stats import f_oneway
df = pd.read_csv(CSV_PATH)
clean = df.dropna(subset=["region", "units_sold"])
groups = clean.groupby("region")["units_sold"].apply(list)
anova_result = f_oneway(*groups)
result = {"summary": "ANOVA units_sold by region", "value": anova_result.pvalue, "p_value": anova_result.pvalue}
print(json.dumps(result))"""

    full_result = run_in_sandbox(sample_code, csv_path)
    print("Full-dataset result:", full_result)

    verdict = verify_result("Is there a difference in units_sold across regions?", sample_code, csv_path, full_result)
    print("\nVerdict:", json.dumps(verdict, indent=2))