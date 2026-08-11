"""
day8_ui_agent_evalsuite.py
(pair file: day8_ui_agent_core.py)
 
=============================================================================
THEORY - WHAT THIS FILE IS AND WHY IT EXISTS
=============================================================================
This is Step 3 of "completing the single agent" (after Days 1-7 proved the
mechanics on one page, and day8_ui_agent_core.py turned that into a
reusable function). Real research on moving agents from prototype to
production-grade points to one specific thing as the actual dividing
line: a structured EVAL SUITE - a small, fixed set of test cases with
KNOWN EXPECTED OUTCOMES, run against the agent to check whether it
genuinely generalizes, not just repeats one memorized success.
 
Every proof across Days 1-7 was the SAME page, run seven times. That's
zero evidence of generalization - just seven confirmations of the same
thing. This file runs the SAME engine against three deliberately different
scenarios instead:
 
  Case 1 - the original login page (regression baseline - must still pass)
  Case 2 - a totally different login page (different DOM, same goal wording -
           proves the brain reasons from what it sees, not a memorized page)
  Case 3 - a dropdown, not a login form at all (deliberately the hard case -
           the current action schema has no "select" action for a native
           <select> element, so this may genuinely expose a real gap - and
           that's the actual POINT of an eval suite: finding what's
           missing, not just confirming what already works)
 
IMPORTANT - NOT LINKED TO DAYS 1-7: the only import in this file is from
day8_ui_agent_core.py (its own pair file, Step 2's work). Nothing here
touches or calls any of the day1 through day7 files.
=============================================================================
"""
 
import json
from day8_ui_agent_core import run_agent
 
TEST_CASES = [
    {
        "name": "Case 1 - Regression baseline (original login)",
        "goal": "Log in with valid credentials and verify successful login",
        "url": "https://rahulshettyacademy.com/loginpagePractise/",
        "expected_verdict": "pass",
        "note": "Already proven across Days 1-7. Must still pass after this refactor."
    },
    {
        "name": "Case 2 - Same goal, completely different page",
        "goal": "Log in with valid credentials and verify successful login",
        "url": "https://the-internet.herokuapp.com/login",
        "expected_verdict": "pass",
        "note": "Different DOM, different field names, different site entirely. "
                "Credentials are shown directly on the page, same as Case 1's pattern."
    },
    {
        "name": "Case 3 - Different interaction type (dropdown)",
        "goal": "Select Option 2 from the dropdown and verify it is selected",
        "url": "https://the-internet.herokuapp.com/dropdown",
        "expected_verdict": "pass",
        "note": "Originally exposed a real gap: no 'select' action existed for native "
                "<select> dropdowns (click/type don't work on them). Now fixed in "
                "day8_ui_agent_core.py - this case should genuinely pass, and stays "
                "in the suite as a regression check for that fix going forward."
    },
]
 
results = []
 
for case in TEST_CASES:
    print(f"\n{'=' * 70}")
    print(f"RUNNING: {case['name']}")
    print(f"Goal: {case['goal']}")
    print(f"URL:  {case['url']}")
    print(f"{'=' * 70}")
 
    result = run_agent(goal=case["goal"], start_url=case["url"])
    result["name"] = case["name"]
    result["expected_verdict"] = case["expected_verdict"]
    result["note"] = case["note"]
    results.append(result)
 
# --- Summary report -----------------------------------------------------
print("\n\n" + "=" * 70)
print("EVAL SUITE SUMMARY")
print("=" * 70)
 
for r in results:
    match = "MATCH" if r["verdict"] == r["expected_verdict"] else "MISMATCH (or expected-unknown)"
    print(f"\n{r['name']}")
    print(f"  Expected : {r['expected_verdict']}")
    print(f"  Actual   : {r['verdict']}  ({match})")
    print(f"  Reflection: {r['reflection']['reflected_verdict']} - {r['reflection']['notes']}")
    print(f"  Turns used: {r['turns_used']}")
 
# Save full detailed results to disk too, not just console - this is the
# start of the "structured report" gap mentioned earlier (Step 6).
with open("eval_suite_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print("\nFull results saved to eval_suite_results.json")