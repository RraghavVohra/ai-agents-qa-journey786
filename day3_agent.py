"""
DAY 3 — Turning JSON into real Playwright TypeScript files

Yesterday we saved 3 structured test cases into test_cases.json.
Today: turn each one into an actual .spec.ts file your Playwright
TS framework could run.

Important honesty check before we start: the JSON only has
PLAIN-ENGLISH steps ("Click the Login button"), not real selectors
like `page.locator('#login-btn')`. The model has never seen your
app's DOM, so it CANNOT know the real selector. If we let it guess
one, it would just be making it up — and a fake selector is worse
than no selector, because it looks like it works until it doesn't.

So today's honest version: generate a proper Playwright TS test
shell, with each step written as a clear comment marking exactly
what needs a real locator. This is a SCAFFOLD, not a finished test.
Filling in real selectors is a later, separate problem — the same
one Project 2 (self-healing locators) exists to solve properly.

Today's story, step by step:
  1. Read test_cases.json (created on Day 2)
  2. For each test case, build a valid Playwright TS test() block
  3. Turn each step into a clearly-marked TODO comment
  4. Write one .spec.ts file per test case into a tests/ folder
"""

import json
import os
import re


def slugify(title: str) -> str:
    """Turn 'Search for a product by name' into 'search_for_a_product_by_name' for a filename."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def generate_playwright_ts(test_case: dict) -> str:
    """Build a Playwright TS test file as a string, from one test_case dict."""
    title = test_case["title"]
    steps = test_case["steps"]
    expected_result = test_case["expected_result"]

    # Each plain-English step becomes a comment, numbered, so a human
    # can walk in and replace each one with a real Playwright action.
    step_comments = "\n".join(
        f"  // Step {i + 1}: {step}" for i, step in enumerate(steps)
    )

    return f"""import {{ test, expect }} from '@playwright/test';

test('{title}', async ({{ page }}) => {{
{step_comments}

  // Expected result: {expected_result}
  // TODO: replace the step comments above with real Playwright actions
  // (page.goto, page.locator(...).click(), page.fill(...), expect(...).toBeVisible())
  // once real selectors for your app are known.
}});
"""


# ── STEP 1: Read yesterday's output ─────────────────────────────────
with open("test_cases.json") as f:
    test_cases = json.load(f)

# ── STEP 2–4: Build one .spec.ts file per test case ─────────────────
os.makedirs("tests", exist_ok=True)

for tc in test_cases:
    filename = f"tests/{slugify(tc['title'])}.spec.ts"
    with open(filename, "w") as f:
        f.write(generate_playwright_ts(tc))
    print(f"✅ Created {filename}")

print(f"\n📁 {len(test_cases)} scaffold test files written to ./tests/")