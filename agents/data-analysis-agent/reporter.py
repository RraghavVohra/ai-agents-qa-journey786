"""
reporter.py -- Step 7 of the Data-Analysis Agent

Ties together every component built so far into the full pipeline, and
compiles the results into one clean, readable report.

Profiler -> Explorer -> [Analyst -> Verifier -> Evidence] per hypothesis -> Report

This supersedes runner.py as the real entry point now that Verifier and
Evidence exist. runner.py is kept as-is on purpose -- a record of what
step 4 alone looked like, before those pieces were built.
"""

import sys
import json

from profiler import load_dataset, profile_dataset
from explorer import generate_hypotheses
from analyst import analyze_hypothesis
from verifier import verify_result
from evidence import build_evidence


def run_full_pipeline(csv_path: str) -> list:
    df = load_dataset(csv_path)
    profile = profile_dataset(df)
    hypotheses = generate_hypotheses(profile)

    print(f"Testing {len(hypotheses)} hypotheses...\n")

    evidence_list = []
    for i, hypothesis in enumerate(hypotheses, start=1):
        print(f"[{i}/{len(hypotheses)}] {hypothesis}")

        try:
            analyst_result = analyze_hypothesis(hypothesis, profile, csv_path)
        except Exception as e:
            analyst_result = {"success": False, "error": f"unexpected exception: {e}"}

        # Only worth running the Verifier's split-testing if the Analyst
        # actually produced something. verify_result() already handles a
        # failed analyst_result safely, but skipping it here saves real
        # time (each split rerun costs ~20-40s thanks to scipy import)
        # when we already know it failed.
        if analyst_result.get("success"):
            verifier_result = verify_result(analyst_result["code"], csv_path, analyst_result)
        else:
            verifier_result = {"verdict": "rejected", "reason": analyst_result.get("error", "execution failed")}

        ev = build_evidence(hypothesis, analyst_result, verifier_result)
        evidence_list.append(ev)

        print(f"    -> {ev.verdict} ({ev.confidence} confidence)\n")

    return evidence_list


def print_report(evidence_list: list):
    verified = [e for e in evidence_list if e.verdict == "verified"]
    rejected = [e for e in evidence_list if e.verdict == "rejected"]

    print("=" * 60)
    print(f"DATA ANALYSIS REPORT -- {len(verified)} verified, {len(rejected)} rejected")
    print("=" * 60)

    if verified:
        print("\nVERIFIED FINDINGS:\n")
        for e in verified:
            print(f"- {e.hypothesis}")
            print(f"  Method: {e.method}")
            print(f"  Confidence: {e.confidence}")
            print(f"  Reason: {e.reason}\n")

    if rejected:
        print("REJECTED (not enough evidence to trust):\n")
        for e in rejected:
            print(f"- {e.hypothesis}")
            print(f"  Reason: {e.reason}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python reporter.py <path_to_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    evidence_list = run_full_pipeline(csv_path)

    print_report(evidence_list)

    print("\nRaw JSON (useful later for the eval harness):")
    print(json.dumps([e.to_dict() for e in evidence_list], indent=2))