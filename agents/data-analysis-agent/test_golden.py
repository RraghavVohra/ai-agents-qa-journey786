"""
test_golden.py -- Step 8 (part 2): Golden Eval Test

The actual proof that the Verifier (step 5) does real work, not just
theater. Runs two KNOWN hypotheses -- bypassing the Explorer entirely,
since we already know exactly which patterns we planted -- straight
through the Analyst's sandbox and the Verifier's split-test logic.

Pass condition:
  - The REAL pattern (channel -> units_sold) must be VERIFIED.
  - The FAKE pattern (segment -> engagement_score) must be REJECTED,
    even though it looks highly significant on the full dataset alone.

If this test ever starts failing after a future change to analyst.py or
verifier.py, that change broke the core value proposition of this whole
agent -- run this before trusting any other change.
"""

import json
from golden_dataset import generate_golden_dataset
from analyst import run_in_sandbox
from verifier import verify_result

CSV_PATH = "golden_dataset.csv"

REAL_PATTERN_CODE = """import pandas as pd
from scipy.stats import f_oneway
df = pd.read_csv(CSV_PATH)
groups = df.groupby("channel")["units_sold"].apply(list)
r = f_oneway(*groups)
result = {"summary": "ANOVA units_sold by channel", "value": r.pvalue, "p_value": r.pvalue}
print(json.dumps(result))"""

FAKE_PATTERN_CODE = """import pandas as pd
from scipy.stats import f_oneway
df = pd.read_csv(CSV_PATH)
groups = df.groupby("segment")["engagement_score"].apply(list)
r = f_oneway(*groups)
result = {"summary": "ANOVA engagement_score by segment", "value": r.pvalue, "p_value": r.pvalue}
print(json.dumps(result))"""


def run_golden_eval():
    generate_golden_dataset(CSV_PATH)

    print("--- REAL pattern (channel -> units_sold) ---")
    real_full = run_in_sandbox(REAL_PATTERN_CODE, CSV_PATH)
    print("Full-dataset p-value:", real_full["result"]["p_value"])
    real_verdict = verify_result(REAL_PATTERN_CODE, CSV_PATH, real_full)
    print("Verdict:", json.dumps(real_verdict, indent=2))

    print("\n--- FAKE pattern (segment -> engagement_score) ---")
    fake_full = run_in_sandbox(FAKE_PATTERN_CODE, CSV_PATH)
    print("Full-dataset p-value:", fake_full["result"]["p_value"], "(looks significant, but is not real)")
    fake_verdict = verify_result(FAKE_PATTERN_CODE, CSV_PATH, fake_full)
    print("Verdict:", json.dumps(fake_verdict, indent=2))

    print()
    assert real_verdict["verdict"] == "verified", "FAIL: the real pattern should have been verified!"
    assert fake_verdict["verdict"] == "rejected", "FAIL: the fake pattern should have been rejected!"
    print("PASS -- Verifier correctly told the real pattern from the fake one.")


if __name__ == "__main__":
    run_golden_eval()