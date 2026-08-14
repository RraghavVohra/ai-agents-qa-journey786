"""
day10_ui_agent_runner.py

Runs a chosen subset of tasks from day10_tasks.py through the engine,
collecting results for human review. No verdict is computed here - each
task's evidence is printed for YOU to read and judge, per the Day 10
Human-in-the-Loop design.

Results accumulate across runs in day10_evidence_report.json - each batch
you run gets ADDED to the report, not overwritten, so it builds up toward
covering all 22 tasks over multiple sessions.
"""

import json
import os
from playwright.sync_api import sync_playwright
from day10_ui_agent_core import run_agent
from day10_tasks import TASKS

# Batch 2: read-only presence checks - no forms, no modals, no external
# redirects yet. Same instinct as the nav batch: group by similar risk
# before moving to the harder, less-proven task types.
TASK_IDS_TO_RUN = [
    "logo-visible",
    "header-contact-info",
    "achievements-visible",
    "testimonials-visible",
    "sebi-disclosure-check",
    "broken-image-check",
]

REPORT_PATH = "day10_evidence_report.json"
if os.path.exists(REPORT_PATH):
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        results = json.load(f)
    print(f"Loaded {len(results)} previously saved result(s) from {REPORT_PATH}")
else:
    results = []

already_done_ids = {r["task_id"] for r in results}
selected_tasks = [
    t for t in TASKS
    if t["id"] in TASK_IDS_TO_RUN and t["id"] not in already_done_ids
]
if len(selected_tasks) < len(TASK_IDS_TO_RUN):
    skipped = set(TASK_IDS_TO_RUN) - {t["id"] for t in selected_tasks}
    print(f"Skipping already-completed task(s): {sorted(skipped)}")

new_results = []

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
        new_results.append(result)
        results.append(result)

    shared_page.close()
    shared_context.close()
    shared_browser.close()

# --- Human review summary - only THIS run's new results, not a reprint of
# everything already reviewed in prior sessions ------------------------------
print("\n\n" + "=" * 70)
print(f"EVIDENCE FOR HUMAN REVIEW (this run - {len(new_results)} task(s))")
print("=" * 70)

for r in new_results:
    print(f"\n--- {r['task_id']} ---")
    print(f"Completion status: {r['agent_completion_status']} (operational only, not a verdict)")
    print(f"Actions completed: {r['evidence']['actions_completed']}")
    print(f"Evidence observed: {r['evidence']['evidence_observed']}")
    print(f"Gaps/concerns    : {r['evidence']['gaps_or_concerns']}")
    print(f"Turns used       : {r['turns_used']}")

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print(f"\nTotal progress: {len(results)}/{len(TASKS)} tasks covered.")
print(f"Full evidence saved to {REPORT_PATH}")