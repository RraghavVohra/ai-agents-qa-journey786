"""
day10_ui_agent_runner.py

Runs a chosen subset of tasks from day10_tasks.py through the engine,
collecting results for human review. No verdict is computed here - each
task's evidence is printed for YOU to read and judge, per the Day 10
Human-in-the-Loop design.

Currently set to the 4 nav tasks - confirming the URL-assert fix
generalizes across all of them before running the full 22-task batch.
"""

import json
from playwright.sync_api import sync_playwright
from day10_ui_agent_core import run_agent
from day10_tasks import TASKS

# Confirming the URL-assert fix generalizes before the full batch -
# same instinct as Day 8's eval suite: prove it more than once.
TASK_IDS_TO_RUN = ["nav-home", "nav-about", "nav-content", "nav-contact"]

selected_tasks = [t for t in TASKS if t["id"] in TASK_IDS_TO_RUN]

results = []

# ONE browser + ONE context + ONE page for the whole batch. Genuinely one
# tab, reused task after task - each task still starts clean because
# run_agent() always calls page.goto(start_url) first, forcing a real
# reload regardless of what the previous task left on the page.
with sync_playwright() as p:
    shared_browser = p.chromium.launch(headless=False)
    shared_context = shared_browser.new_context()
    shared_page = shared_context.new_page()

    for task in selected_tasks:
        print(f"\n{'=' * 70}")
        print(f"RUNNING: {task['id']}")
        print(f"Goal: {task['goal']}")
        print(f"Acceptance criteria: {task['acceptance_criteria']}")
        print(f"{'=' * 70}")

        result = run_agent(
            goal=task["goal"],
            start_url=task["start_url"],
            acceptance_criteria=task["acceptance_criteria"],
            browser=shared_browser,
            context=shared_context,
            page=shared_page
        )
        result["task_id"] = task["id"]
        results.append(result)

    shared_page.close()
    shared_context.close()
    shared_browser.close()

# --- Human review summary - no verdict, just organized evidence ------------
print("\n\n" + "=" * 70)
print("EVIDENCE FOR HUMAN REVIEW")
print("=" * 70)

for r in results:
    print(f"\n--- {r['task_id']} ---")
    print(f"Completion status: {r['agent_completion_status']} (operational only, not a verdict)")
    print(f"Actions completed: {r['evidence']['actions_completed']}")
    print(f"Evidence observed: {r['evidence']['evidence_observed']}")
    print(f"Gaps/concerns    : {r['evidence']['gaps_or_concerns']}")
    print(f"Turns used       : {r['turns_used']}")

with open("day10_evidence_report.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print("\nFull evidence saved to day10_evidence_report.json")