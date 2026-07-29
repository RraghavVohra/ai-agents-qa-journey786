"""
PROJECT 2 — Self-Healing Locators
Script 2: Auto-extract broken selectors from result.json

Until now, YOU read the error and typed the broken selector into
Python by hand. That doesn't scale to 150-200 tests. Today: teach
Python to find failures itself, straight from Playwright's own
JSON report.

Today's story, step by step:
  1. Load result.json (Playwright's JSON reporter output)
  2. Walk through suites -> specs -> tests -> results, looking for
     anything that didn't pass
  3. Playwright's own error message contains the exact broken
     selector, e.g. "waiting for locator('#usernme')" — pull that
     out with a regex instead of eyeballing it
  4. Build a clean list: {spec title, file, line, broken selector}
     — this list is what tomorrow's healer script will loop over
"""

import json
import re

with open("result.json", "r", encoding="utf-8") as f:
    report = json.load(f)

failures = []

for suite in report["suites"]:
    for spec in suite["specs"]:
        if spec["ok"]:
            continue  # this spec passed — nothing to heal

        for test in spec["tests"]:
            for result in test["results"]:
                if result["status"] == "passed":
                    continue

                for error in result.get("errors", []):
                    message = error.get("message", "")

                    # Playwright's own wording: "waiting for locator('...')"
                    # This regex pulls out whatever's inside the quotes.
                    match = re.search(r"waiting for locator\('([^']+)'\)", message)
                    if not match:
                        continue  # some failures aren't locator-related at all

                    location = error.get("location", {})
                    failures.append({
                        "spec_title": spec["title"],
                        "file": location.get("file"),
                        "line": location.get("line"),
                        "broken_selector": match.group(1)
                    })

print(f"Found {len(failures)} broken-locator failure(s):\n")
print(json.dumps(failures, indent=2))