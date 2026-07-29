"""
PROJECT 2 — Self-Healing Locators
Script 5: The full pipeline, wired together
(v4 — now opens a PR instead of writing directly to the file)

This combines everything so far into one run:
  1. Parse result.json -> find broken-locator failures (Script 2's job)
  2. For each failure, open the actual .spec.ts file and grab the
     comment just above the broken line -> that's our "intent",
     extracted automatically instead of typed by hand
  3. Load the LIVE DOM snapshot captured by fixtures.ts at the exact
     moment this specific test failed (no more stale, pre-saved file)
  4. Ask the model to propose a fix for each failure
  5. If confidence is "high": isolate the fix on its own git branch,
     commit it there, push, and open a PR via GitHub CLI — instead
     of rewriting main directly. A human still reviews and merges.
     Medium/low confidence just gets printed for manual review.

This is the CI-safe version: nothing ever lands on main without a
human clicking "merge," which matters once this runs inside a real
pipeline instead of on your own machine.
"""

import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()


# ── Step 1: Parse result.json (same logic as Script 2) ──────────────
def get_broken_locator_failures(report_path="result.json"):
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    failures = []
    for suite in report["suites"]:
        for spec in suite["specs"]:
            if spec["ok"]:
                continue
            for test in spec["tests"]:
                for result in test["results"]:
                    if result["status"] == "passed":
                        continue
                    for error in result.get("errors", []):
                        match = re.search(r"waiting for locator\('([^']+)'\)", error.get("message", ""))
                        if not match:
                            continue
                        location = error.get("location", {})
                        failures.append({
                            "spec_title": spec["title"],
                            "file": location.get("file"),
                            "line": location.get("line"),
                            "broken_selector": match.group(1)
                        })
    return failures


# ── Step 2: Extract intent from the comment above the broken line ──
def extract_intent(file_path: str, line_number: int) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # line_number is 1-indexed from Playwright; look at the line just above it
    comment_line = lines[line_number - 2].strip() if line_number >= 2 else ""

    if comment_line.startswith("//"):
        return comment_line.lstrip("/").strip()
    return "No comment found — intent unknown, may need a human to clarify"


# ── Step 3: Load the DOM snapshot for THIS specific failing test ────
def slugify(title: str) -> str:
    """Must match the naming logic in fixtures.ts exactly, or the
    filenames won't line up between the TS side and the Python side."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def load_dom(spec_title: str, max_chars=15000) -> str:
    """
    Load the LIVE snapshot captured by fixtures.ts at the moment this
    specific test failed — not a stale, separately-run file. Each
    failing test gets its own dom_snapshot_<test_name>.html.
    """
    snapshot_path = f"dom_snapshot_{slugify(spec_title)}.html"
    with open(snapshot_path, "r", encoding="utf-8") as f:
        html = f.read()
    return html[:max_chars]


# ── Step 4: Ask the model to propose a fix (same tool as Script 1) ──
tools = [
    {
        "type": "function",
        "function": {
            "name": "propose_fixed_locator",
            "description": "Propose a corrected CSS selector for a broken Playwright locator, based on real page HTML.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fixed_selector": {"type": "string", "description": "The corrected CSS selector"},
                    "reasoning": {"type": "string", "description": "Why this element matches the intent"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
                },
                "required": ["fixed_selector", "reasoning", "confidence"]
            }
        }
    }
]


def propose_fix(broken_selector: str, intent: str, page_html: str) -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a self-healing test automation agent. Given a broken "
                "selector, its intended purpose, and the current real page HTML, "
                "propose the correct selector. Always use the propose_fixed_locator tool."
            )
        },
        {
            "role": "user",
            "content": f"Broken selector: {broken_selector}\nIntent: {intent}\n\nCurrent page HTML:\n{page_html}"
        }
    ]
    response = client.chat.completions.create(
        model="gpt-4o", messages=messages, tools=tools, tool_choice="auto"
    )
    call = response.choices[0].message.tool_calls[0]
    return json.loads(call.function.arguments)


# ── Step 5: Write the fix to the file (used internally by Step 6 —
# runs on the isolated branch, never directly on main) ──────────────
def apply_fix(file_path: str, broken_selector: str, fixed_selector: str) -> bool:
    """
    Replace the broken selector with the fixed one, directly in the
    real .spec.ts file. Returns True if a replacement actually happened.

    Safety net: before touching the real file, we save an untouched
    copy as file.bak — so a wrong auto-fix is always reversible.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    old_locator = f"'{broken_selector}'"
    new_locator = f"'{fixed_selector}'"

    if old_locator not in content:
        return False  # nothing matched — don't touch the file

    backup_path = file_path + ".bak"
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(content)

    content = content.replace(old_locator, new_locator)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return True


# ── Step 6: Open a PR instead of touching main directly ──────────────
import subprocess
import datetime


def create_healing_pr(file_path: str, broken_selector: str, fixed_selector: str,
                       reasoning: str, test_title: str) -> None:
    """
    CI-safe version of apply_fix: instead of rewriting the file on
    whatever branch we're currently on (which could be main), isolate
    the change on its own branch, push it, and open a PR. Nothing
    reaches main without a human reviewing and clicking merge.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    branch_name = f"auto-heal/{slugify(test_title)}-{timestamp}"

    def run(cmd):
        print(f"   $ {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    run(["git", "checkout", "-b", branch_name])
    apply_fix(file_path, broken_selector, fixed_selector)  # reuses Step 5's function
    run(["git", "add", file_path])
    run(["git", "commit", "-m", f"Self-heal: {broken_selector} -> {fixed_selector} in {test_title}"])
    run(["git", "push", "-u", "origin", branch_name])
    run([
        "gh", "pr", "create",
        "--title", f"Self-heal: fix broken locator in {test_title}",
        "--body", (
            f"**Broken selector:** `{broken_selector}`\n"
            f"**Fixed selector:** `{fixed_selector}`\n"
            f"**AI reasoning:** {reasoning}\n\n"
            f"Auto-generated by heal_pipeline.py — please review before merging."
        ),
        "--base", "main",
        "--head", branch_name
    ])
    run(["git", "checkout", "main"])


# ── Run the full pipeline ────────────────────────────────────────────
failures = get_broken_locator_failures()
print(f"Found {len(failures)} broken-locator failure(s)\n")

for failure in failures:
    intent = extract_intent(failure["file"], failure["line"])
    page_html = load_dom(failure["spec_title"])
    fix = propose_fix(failure["broken_selector"], intent, page_html)

    print(f"📍 {failure['spec_title']} (line {failure['line']})")
    print(f"   Broken: {failure['broken_selector']}")
    print(f"   Intent (auto-extracted): {intent}")
    print(f"   Proposed fix: {json.dumps(fix, indent=2)}")

    # Only auto-apply when the model is confident — same caution as
    # Project 1's suggest-mode. Medium/low confidence gets flagged
    # for a human to review instead of silently changing test code.
    if fix["confidence"] == "high":
        create_healing_pr(
            failure["file"], failure["broken_selector"], fix["fixed_selector"],
            fix["reasoning"], failure["spec_title"]
        )
        print(f"   ✅ Opened a PR with the fix on its own branch (main untouched)")
    else:
        print(f"   ⏸ Confidence '{fix['confidence']}' — not auto-applied, review manually")

    print()