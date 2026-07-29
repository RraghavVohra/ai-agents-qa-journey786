"""
PROJECT 2 — Self-Healing Locators
Script 3: The full pipeline, wired together

This combines everything so far into one run:
  1. Parse result.json -> find broken-locator failures (Script 2's job)
  2. For each failure, open the actual .spec.ts file and grab the
     comment just above the broken line -> that's our "intent",
     extracted automatically instead of typed by hand
  3. Load the current DOM snapshot (Script 1's job)
  4. Ask the model to propose a fix for each failure

Known limitation, on purpose, not hidden: dom_snapshot.html was
captured separately, not at the exact moment of failure. That's fine
for this login page (nothing on it changes), but a fully real system
would capture the DOM live, at failure time. That's a deliberate next
upgrade, not something to solve today.
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


# ── Step 3: Load the current DOM snapshot ────────────────────────────
def load_dom(snapshot_path="dom_snapshot.html", max_chars=15000) -> str:
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


# ── Run the full pipeline ────────────────────────────────────────────
failures = get_broken_locator_failures()
print(f"Found {len(failures)} broken-locator failure(s)\n")

for failure in failures:
    intent = extract_intent(failure["file"], failure["line"])
    page_html = load_dom()
    fix = propose_fix(failure["broken_selector"], intent, page_html)

    print(f"📍 {failure['spec_title']} (line {failure['line']})")
    print(f"   Broken: {failure['broken_selector']}")
    print(f"   Intent (auto-extracted): {intent}")
    print(f"   Proposed fix: {json.dumps(fix, indent=2)}\n")