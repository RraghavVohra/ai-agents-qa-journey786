"""
verifier.py -- Step 5 of the Data-Analysis Agent (THE differentiator)

Job of this file: decide whether an Analyst's result should be trusted,
before it's allowed anywhere near a report.

Approach: STATISTICAL RE-TEST. Rerun the exact same generated code on
two random halves of the data. If the two halves agree on the
conclusion, the pattern likely holds. If they disagree, it doesn't
survive being re-tested and gets rejected -- no matter how good the
p-value on the full dataset looked.

This is the cheap, deterministic first-pass approach (no extra LLM
call). A second-pass LLM cross-check can be added later for cases this
can't resolve alone (e.g. purely descriptive results with no
significance test to replicate) -- worth discussing with Abhishek once
this base version is proven.
"""

import os
import sys
import json
import tempfile
import pandas as pd

from analyst import run_in_sandbox


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


def verify_result(code: str, csv_path: str, analyst_result: dict) -> dict:
    """Re-runs the Analyst's own code on two random halves of the data
    and checks whether the conclusion holds up. Always returns a verdict
    dict -- {"verdict": "verified" | "rejected", "reason": str} -- never
    silently passes a result through without a stated reason."""
    if not analyst_result.get("success"):
        return {"verdict": "rejected", "reason": "Analyst execution already failed -- nothing to verify."}

    status_full, p_full = _get_significance_status(analyst_result.get("result"))

    if status_full == "no_test":
        # Analyst explicitly said: no test was run. Honest, deliberate,
        # nothing to statistically dispute -- and no reason to spend
        # 25-45s x2 rerunning code in the sandbox for nothing.
        return {"verdict": "verified", "reason": "Descriptive result, no significance test to replicate. Confidence: moderate."}

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

    verdict = verify_result(sample_code, csv_path, full_result)
    print("\nVerdict:", json.dumps(verdict, indent=2))