# UI Testing Agent

An autonomous QA agent that takes a plain-English goal and a starting URL, and figures out **on its own** how to achieve it in a real browser — no hardcoded selectors, no scripted steps, anywhere.

```
Goal: "Log in with valid credentials and verify successful login"
URL:  https://example.com/login
        |
        v
   Agent decides, acts, observes, remembers, and reports pass/fail - autonomously
```

Part of a self-directed journey building AI agents for QA automation from scratch, following an Atomic Habits approach: small, isolated daily proofs before wiring anything into a live loop.

---

## What it actually does

1. **Observe** — reads the real, live DOM of whatever page it's currently on
2. **Decide** — an LLM call (GPT-4o) picks exactly ONE next action toward the goal, in plain English (e.g. "the username field"), based on everything it's seen and tried so far in this run
3. **Resolve** — a second LLM call turns that plain-English description into a real CSS selector on the live page (reused from a self-healing locator agent built earlier in this journey)
4. **Act** — Playwright executes the action for real, on a real browser
5. **Repeat**, until the agent itself decides the goal is achieved (`done`), has genuinely failed (`fail`), or a safety cap is hit
6. **Reflect** — a second, independent LLM call reviews the entire trail afterward and gives its own verdict, catching cases where the agent said "pass" but something it intended to do quietly never completed

---

## Architecture

| Layer | Role | Stays stateless? |
|---|---|---|
| **Brain** (`perform_next_action`) | Decides the next single action | No — carries full conversation history (ReAct) |
| **Hands** (`resolve_selector`) | Turns plain English into a real selector | Yes, deliberately — doesn't need memory of past turns |
| **Eyes** (`get_live_dom`) | Reads the live page, syncs value/checked/selected state that raw HTML doesn't reflect on its own | N/A |
| **Reviewer** (`reflect_on_trail`) | Second, independent look at the finished trail | Runs once, after the loop ends |

**Why the Brain has memory and the Hands don't:** turning "the username field" into a selector only ever needs the current page — it gains nothing from remembering turn 1. Deciding what to do next, though, genuinely benefits from knowing what was already tried and what happened. Memory belongs where it's useful, not everywhere by default.

---

## The journey (Days 1-8)

| Day | Proved | File(s) |
|---|---|---|
| 1-3 | The brain alone: correct first action, adapts mid-flow, recognizes "done" - all on static snapshots, no browser | `day1_ui_agent.py` - `day3_ui_agent.py` |
| 4 | One real decide→resolve→act→observe cycle, live browser, for the first time | `day4_ui_agent.py` |
| 5 | Wrapped into an actual repeat-until-done loop, with a safety cap | `day5_ui_agent.py` |
| 6 | **ReAct** - one growing conversation instead of a fresh stateless call each turn, so the agent can notice and recover from its own mistakes mid-task | `day6_ui_agent_ReAct.py`, `_wrongpassword.py`, `_selfcorrect.py` |
| 7 | **Reflection** - a second reviewer catching cases where "pass" hid an unresolved failure | `day7_ui_agent_reflection.py`, `day7_reflection_isolated.py` |
| 8 | Generalization - parameterized into a reusable engine, proven against 3 genuinely different scenarios via an eval suite, one real gap (dropdowns) found and fixed | `day8_ui_agent_core.py`, `day8_ui_agent_evalsuite.py` |

Earlier day-numbered files are kept intentionally, not deleted - they're the audit trail of how each mechanic was proven in isolation before being trusted in the full loop.

---

## Setup

```powershell
cd agents/ui-testing-agent
python -m venv venv
venv\Scripts\activate
pip install openai python-dotenv playwright
playwright install chromium
```

Create a `.env` file in this folder:
```
OPENAI_API_KEY=your_key_here
```

---

## Running it

**Single run, quick check:**
```powershell
python day8_ui_agent_core.py
```

**Full eval suite (recommended - proves generalization, not just one page):**
```powershell
python day8_ui_agent_evalsuite.py
```

**As a reusable function, from your own script:**
```python
from day8_ui_agent_core import run_agent

result = run_agent(
    goal="Log in with valid credentials and verify successful login",
    start_url="https://example.com/login"
)
print(result["verdict"], result["reflection"])
```

---

## The eval suite

Three deliberately different cases, not just the same page run repeatedly - a fixed, structured way to check the agent actually generalizes, not just memorized one form:

- **Case 1** - the original login page (regression baseline)
- **Case 2** - a completely different login page (different DOM, same goal - proves it reasons from what it sees)
- **Case 3** - a native dropdown, not a login form at all (this originally exposed a real gap - no `select` action existed for `<select>` elements - now fixed)

Results are saved to `eval_suite_results.json` after every run.

---

## Known limitations / deliberate trade-offs

- **Success detection sometimes relies on URL change alone**, without always asserting on specific page text. Reflection has flagged this as worth tightening in some cases (e.g. Case 2). Deliberately left as-is for now rather than forcing an `assert` on every run - some real pages have no explicit success text at all, and over-constraining this risked breaking generalization to those pages. Documented here as a conscious choice, not an oversight.
- **Non-determinism is real and expected.** The same forced failure has, across different runs, produced explicit acknowledgment-and-retry, silent retry, and silent abandonment of a step. This is inherent to LLM-driven decisions, not a bug in this code - worth remembering when reading any single run's trail as representative.
- **Only tested against simple form-based flows so far** (logins, dropdowns). Not yet proven against multi-step wizards, file uploads, drag-and-drop, or authentication popups.
- **`resolve_selector` has no self-healing loop of its own within a run** - if it returns a bad selector, the failure is caught and fed back to the brain (which can retry), but there's no dedicated retry-with-different-strategy logic at the resolver level itself.

---

## What's next

- **Long-term memory** (Project 4) - everything above is memory *within one run* only; nothing persists once the process ends. Planned: RAG-based memory using the same foundation from an earlier RAG evaluation framework, so the agent can carry real experience across runs, not just within one.
- **Plan-and-Execute** - an alternative to turn-by-turn ReAct for longer, more predictable multi-step goals.
- **Multi-Agent Collaboration** - the long-term vision: specialized agents handling distinct tasks, not one monolithic agent doing everything.
- Folding the self-healing locator agent into the real production POM-based framework, not just this practice site.

---

## Acknowledgments

ReAct architecture suggested by Abhishek.