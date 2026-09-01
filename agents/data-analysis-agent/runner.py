"""
runner.py -- Step 4 of the Data-Analysis Agent

Ties together everything built so far: Profiler -> Explorer -> Analyst.
Until now, analyst.py only ever tested the FIRST hypothesis, on purpose,
so we could inspect one result closely. Now we loop across ALL of them.

One robustness rule added here that didn't exist before: if analyzing
ONE hypothesis throws an unexpected error (a flaky API call, a network
blip), that should not kill the entire run. We catch it, record it as
failed evidence for that one hypothesis, and keep going -- the whole
point of collecting evidence per-item instead of all-or-nothing.
"""

import sys
import json

from profiler import load_dataset, profile_dataset
from explorer import generate_hypotheses
from analyst import analyze_hypothesis


def run_pipeline(csv_path: str) -> list[dict]:
    """Runs the full pipeline so far: profile once, generate hypotheses
    once, then test every hypothesis one at a time -- each one isolated
    from the others' failures."""
    df = load_dataset(csv_path)
    profile = profile_dataset(df)
    hypotheses = generate_hypotheses(profile)

    print(f"Testing {len(hypotheses)} hypotheses...\n")

    results = []
    for i, hypothesis in enumerate(hypotheses, start=1):
        print(f"[{i}/{len(hypotheses)}] {hypothesis}")

        try:
            result = analyze_hypothesis(hypothesis, profile, csv_path)
        except Exception as e:
            # An unexpected crash (not a normal rejected/failed result --
            # those are already handled inside analyst.py) still becomes
            # evidence, not a dead pipeline.
            result = {
                "hypothesis": hypothesis,
                "success": False,
                "error": f"unexpected exception: {e}",
            }

        results.append(result)
        status = "OK" if result.get("success") else "REJECTED/FAILED"
        print(f"    -> {status}\n")

    return results


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python runner.py <path_to_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    results = run_pipeline(csv_path)

    succeeded = sum(1 for r in results if r.get("success"))
    print(f"Done: {succeeded}/{len(results)} hypotheses produced evidence.\n")
    print(json.dumps(results, indent=2))