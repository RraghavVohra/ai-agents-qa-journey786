"""
ui_testing_agent.py

The consolidated, reusable engine behind everything proven across Days 1-7:
- Observe -> Decide -> Resolve -> Act loop (Days 1-5)
- ReAct memory: one growing conversation instead of stateless per-turn calls (Day 6)
- Reflection: a second, independent review of the finished trail (Day 7)

What's DIFFERENT from day7_ui_agent_reflection.py, and why:
- GOAL and LOGIN_URL are no longer hardcoded constants - they're real
  parameters to run_agent(). A script wired to one page isn't a reusable
  agent, it's a script that happens to work on one page.
- The TEST_FORCE_* debug toggles are gone entirely. That scaffolding did
  its job proving the mechanics (Day 6) - it doesn't belong in the actual
  engine going forward. It still lives on, unchanged, in the dedicated
  day6_ui_agent_ReAct_wrongpassword.py / _selfcorrect.py files as your
  history trail.
- No more input("Press Enter...") pause - this needs to run unattended,
  back to back, across multiple eval suite cases.
- Returns a structured result dict instead of just printing - so a caller
  (like the eval suite) can collect and compare results across many runs.
"""

"""
day8_ui_agent_core.py
(pair file: day8_ui_agent_evalsuite.py)

=============================================================================
THEORY - WHAT THIS FILE IS AND WHY IT EXISTS
=============================================================================
This is Day 8 of the UI Testing Agent project - the "let's actually finish
this properly" phase, after Days 1-7 proved every individual mechanic:

  Day 1-3: the BRAIN alone - given a goal + a page snapshot, correctly
           picks one action, adapts mid-flow, recognizes when done.
  Day 4:   wired in a REAL browser for the first time - one full
           decide -> resolve -> act -> observe cycle, done once.
  Day 5:   wrapped that into an actual REPEATING LOOP until done/fail.
  Day 6:   ReAct memory - one growing conversation instead of a fresh
           stateless call every turn, so the agent can notice and recover
           from its own mistakes mid-task.
  Day 7:   Reflection - a second, independent review pass at the end,
           catching cases where the agent says "pass" but something it
           intended to do quietly never completed.

THE PROBLEM WITH DAYS 1-7: every single one of those was a SCRIPT wired to
ONE specific page (rahulshettyacademy's login form), with the goal and URL
hardcoded as constants. That proved the MECHANICS work, but never proved
they GENERALIZE to a goal or page the agent hasn't been tuned against.

WHAT THIS FILE DOES DIFFERENTLY: takes everything proven in Days 1-7 and
turns it into one reusable function, run_agent(goal, start_url), that can
be pointed at ANY goal and ANY page - not just this one login form. All the
Day-6-specific TEST_FORCE_* debug toggles are gone; that scaffolding did
its job proving the mechanics and now lives on only in its own dedicated
test files (day6_ui_agent_ReAct_wrongpassword.py / _selfcorrect.py).

IMPORTANT - NOT LINKED TO DAYS 1-7: this file does not import, call, or
depend on ANY of the day1 through day7 files. It's a full, standalone
rewrite that consolidates what those days PROVED, not code that reuses
them directly. Nothing here touches those files at all.

WHO USES THIS FILE: day8_ui_agent_evalsuite.py imports run_agent() from
here and calls it multiple times, once per test case, to check whether
this actually generalizes - that's Step 3 of the "complete the agent"
plan. This file can also be run directly (see bottom) for one quick
manual check, same as Days 4-7 always allowed.
=============================================================================
"""

"""
day9_ui_agent_core.py
(pair files: day9_credential_test.py | earlier: day8_ui_agent_core.py + day8_ui_agent_evalsuite.py)

=============================================================================
THEORY - THE FULL STORY, DAYS 1-9
=============================================================================
  Day 1-3: the BRAIN alone - given a goal + a page snapshot, correctly
           picks one action, adapts mid-flow, recognizes when done. No
           browser touched yet.
  Day 4:   wired in a REAL browser for the first time - one full
           decide -> resolve -> act -> observe cycle, done once.
  Day 5:   wrapped that into an actual REPEATING LOOP until done/fail,
           with a safety cap.
  Day 6:   ReAct memory - one growing conversation instead of a fresh
           stateless call every turn, so the agent can notice and recover
           from its own mistakes mid-task.
  Day 7:   Reflection - a second, independent review pass at the end,
           catching cases where the agent says "pass" but something it
           intended to do quietly never completed.
  Day 8:   Generalization - Days 1-7 were all ONE script wired to ONE page
           (rahulshettyacademy's login form) with goal/URL hardcoded as
           constants. Day 8 turned this into a reusable run_agent(goal,
           start_url) function, built an EVAL SUITE (a fixed set of test
           cases with known expected outcomes) against 3 deliberately
           different scenarios, found a real gap (no way to operate a
           native <select> dropdown - click/type don't work on those),
           and fixed it with page.select_option(). Also made 'assert' do
           a REAL check against the live page instead of being a no-op.
  Day 9:   THIS FILE. Every proof through Day 8 relied on the target page
           DISPLAYING its own valid credentials in plain text - true for
           every practice site used so far, never true for a real
           organizational login. The fix: run_agent() now accepts
           optional username/password parameters, injected as an explicit
           override the agent is instructed to always prefer over
           anything it reads on the page. Proven in day9_credential_test.py
           against saucedemo.com, deliberately using a non-obvious valid
           account (problem_user, not the first-listed standard_user) -
           the only real way to prove the agent obeys what it's given
           rather than defaulting to whatever's most visible on the page.

WHAT'S ACTUALLY DIFFERENT IN THIS FILE vs day8_ui_agent_core.py: exactly
one addition - the username/password parameters on run_agent(), and one
reinforcing line in the system prompt telling the brain to always prefer
given credentials over page content. Everything else (the brain, hands,
eyes, reflection) is unchanged from Day 8.

IMPORTANT - NOT LINKED TO DAYS 1-8: this file does not import, call, or
depend on ANY of the day1 through day8 files. It's a full, standalone file
that carries forward what those days proved - day8_ui_agent_core.py is
kept completely untouched as an accurate historical snapshot, not
overwritten. This is the personal versioning pattern used throughout this
whole project: new file per meaningful change, nothing overwritten.

STILL NOT SOLVED BY THIS FILE: every decision still sends the live page's
real HTML to OpenAI's API. That's a separate, unresolved data-governance
question - fixing credential handling does not fix that. Not something to
point at a real organizational application without addressing that
question first.
=============================================================================
"""

import os
import json
from playwright.sync_api import sync_playwright
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Brain's tool schema -----------------------------------------------------
decide_tools = [{
    "type": "function",
    "function": {
        "name": "perform_next_action",
        "description": "Decide the single next UI action toward the goal, based on the current page and everything tried so far.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "type", "select", "assert", "done", "fail"]},
                "target_description": {"type": "string"},
                "value": {"type": "string"},
                "reasoning": {"type": "string"}
            },
            "required": ["action", "target_description", "reasoning"]
        }
    }
}]

decide_system_prompt = (
    "You are a UI testing agent working toward a single goal. You will see "
    "the full history of your own past Thoughts, Actions, and their real "
    "Observations in this conversation - use that history. If a past action "
    "did not produce the expected change, do not simply repeat it - reason "
    "about why and try something different. "
    "Decide only the SINGLE next action toward the goal - never plan ahead. "
    "Don't repeat an action whose result you can already see succeeded. "
    "If the goal already looks achieved from the current page, return action "
    "'done'. Real production pages after success don't always show an "
    "explicit 'welcome' message - the URL itself is strong evidence. "
    "If the current URL has changed away from the original page, and there "
    "is no error message visible, treat that as sufficient evidence the "
    "goal is already achieved. "
    "If the current page clearly shows an error message indicating failure "
    "(e.g. rejected credentials), and you have already attempted to submit, "
    "return action 'fail' with your reasoning - do not keep retrying the "
    "exact same submission blindly. "
    "If the element to interact with is a dropdown (a native <select> "
    "element with multiple <option> children), use action 'select' - "
    "target_description should describe the DROPDOWN element itself, not "
    "any individual option, and 'value' should be the exact visible text "
    "of the option to choose (e.g. 'Option 2'). Do not try to 'click' or "
    "'type' directly on individual <option> elements - native dropdown "
    "options are not interactable that way in a real browser. "
    "'assert' now performs a REAL check against the live page - "
    "target_description should describe the element whose text you expect "
    "to contain something, and 'value' should be that expected text. If it "
    "doesn't match, this will genuinely fail and you'll see why - use this "
    "to actually confirm evidence, not just to narrate a conclusion. "
    "If explicit credentials are provided in the goal message, you MUST "
    "use exactly those values for any login - never substitute credentials "
    "you happen to see displayed on the page itself, even if they look "
    "valid. Given credentials always take priority over page content."
)

# --- Hands: resolve_selector, stateless on purpose ---------------------------
resolve_tools = [{
    "type": "function",
    "function": {
        "name": "resolve_selector",
        "description": "Given a plain-English description of a UI element and the real page HTML, return a CSS selector that uniquely targets it.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "A CSS selector that uniquely matches the described element."},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
            },
            "required": ["selector", "confidence"]
        }
    }
}]

resolve_system_prompt = (
    "You are given a plain-English description of a UI element and the real "
    "page HTML. Return one precise CSS selector that uniquely matches that "
    "element on this exact page."
)

def resolve_selector(target_description, dom_html):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": resolve_system_prompt},
            {"role": "user", "content": f"Element description: {target_description}\n\nPage HTML:\n{dom_html}"}
        ],
        tools=resolve_tools,
        tool_choice={"type": "function", "function": {"name": "resolve_selector"}}
    )
    return json.loads(response.choices[0].message.tool_calls[0].function.arguments)


# --- Reflection: second independent review of the finished trail ------------
reflect_tools = [{
    "type": "function",
    "function": {
        "name": "reflect_on_trail",
        "description": "Review a completed test run's full trail and give a reflected verdict, noting any discrepancies for a human QA reviewer.",
        "parameters": {
            "type": "object",
            "properties": {
                "reflected_verdict": {
                    "type": "string",
                    "enum": ["pass", "fail", "pass_with_notes"],
                    "description": "pass_with_notes = the stated goal was achieved, but something worth flagging happened along the way."
                },
                "notes": {
                    "type": "string",
                    "description": "Any discrepancy worth a human QA reviewer knowing - e.g. an intended action that failed and was never retried or confirmed, even if the overall goal still succeeded."
                }
            },
            "required": ["reflected_verdict", "notes"]
        }
    }
}]

reflect_system_prompt = (
    "You are reviewing a completed UI test run's full trail of actions, as a "
    "second reviewer - not the agent that ran it. Carefully check: did every "
    "action the agent INTENDED to take actually succeed, or get properly "
    "retried after a failure? Flag any action that failed and was never "
    "revisited by a later turn, even if the overall goal still appears to "
    "have been achieved by other means. Use 'pass_with_notes' when the goal "
    "was genuinely achieved but something in the trail is still worth a "
    "human QA reviewer knowing about."
)

def reflect_on_trail(goal, trail, original_verdict):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": reflect_system_prompt},
            {"role": "user", "content": (
                f"Goal: {goal}\n\n"
                f"Original verdict from the agent that ran this: {original_verdict}\n\n"
                f"Full trail:\n{json.dumps(trail, indent=2)}"
            )}
        ],
        tools=reflect_tools,
        tool_choice={"type": "function", "function": {"name": "reflect_on_trail"}}
    )
    return json.loads(response.choices[0].message.tool_calls[0].function.arguments)


# --- Observation: live DOM, synced value/checked state, noise stripped ------
def get_live_dom(page, retries=3, retry_delay_ms=500):
    js = """
        () => {
            document.querySelectorAll('input, textarea').forEach(el => {
                if (el.type === 'checkbox' || el.type === 'radio') {
                    if (el.checked) {
                        el.setAttribute('checked', 'checked');
                    } else {
                        el.removeAttribute('checked');
                    }
                } else {
                    el.setAttribute('value', el.value);
                }
            });
            // Same category of bug as checkbox 'checked' - a <select>'s
            // chosen option lives in a live PROPERTY, not the raw HTML
            // 'selected' ATTRIBUTE, which doesn't update on its own after
            // select_option() runs. Applying this fix proactively now,
            // rather than waiting to rediscover the same lesson a third time.
            document.querySelectorAll('select').forEach(sel => {
                Array.from(sel.options).forEach(opt => {
                    if (opt.selected) {
                        opt.setAttribute('selected', 'selected');
                    } else {
                        opt.removeAttribute('selected');
                    }
                });
            });
            const clone = document.documentElement.cloneNode(true);
            clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
            return clone.outerHTML;
        }
    """
    last_error = None
    for attempt in range(retries):
        try:
            return page.evaluate(js)
        except Exception as e:
            last_error = e
            if "Execution context was destroyed" in str(e) or "navigation" in str(e).lower():
                page.wait_for_timeout(retry_delay_ms)
                continue
            raise
    raise last_error


# --- The reusable engine -----------------------------------------------------
def run_agent(goal, start_url, username=None, password=None, max_turns=6, headless=False):
    """
    Runs the full ReAct + Reflection loop for a given goal and starting URL.

    username/password: if provided, the agent is explicitly instructed to
    use EXACTLY these values for any login - overriding anything it might
    otherwise read off the page. This is the Day 9 fix: every proof through
    Day 8 relied on the target page displaying its own valid credentials,
    which a real login never will. Passing credentials in here, rather than
    letting the agent discover them, is what makes this usable beyond
    practice sites.

    Returns a dict: {goal, start_url, verdict, reflection, trail, turns_used}
    """
    credential_note = ""
    if username is not None or password is not None:
        credential_note = (
            f"\n\nUse EXACTLY these credentials for any login on this page: "
            f"username='{username}', password='{password}'. Do NOT use any "
            f"other username or password, even if the page itself displays "
            f"other valid-looking examples - use ONLY the credentials given "
            f"here, exactly as provided."
        )

    messages = [
        {"role": "system", "content": decide_system_prompt},
        {"role": "user", "content": f"Goal: {goal}{credential_note}"}
    ]

    trail = []
    verdict = "inconclusive"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(start_url)

        for turn in range(1, max_turns + 1):
            print(f"\n--- Turn {turn} ---")

            live_dom = get_live_dom(page)
            current_url = page.url

            messages.append({
                "role": "user",
                "content": f"Current URL: {current_url}\n\nCurrent page HTML:\n{live_dom}"
            })

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=decide_tools,
                tool_choice={"type": "function", "function": {"name": "perform_next_action"}}
            )
            assistant_msg = response.choices[0].message
            tool_call = assistant_msg.tool_calls[0]
            action = json.loads(tool_call.function.arguments)
            print("Decided:", json.dumps(action, indent=2))

            messages.append({
                "role": "assistant",
                "content": assistant_msg.content,
                "tool_calls": [{
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }]
            })

            turn_record = {"turn": turn, "decision": action}

            if action["action"] == "done":
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "Agent concluded the goal is achieved. No action taken."
                })
                verdict = "pass"
                trail.append(turn_record)
                break

            if action["action"] == "fail":
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "Agent concluded the goal has failed. No further action taken."
                })
                verdict = "fail"
                trail.append(turn_record)
                break

            try:
                resolved = resolve_selector(action["target_description"], live_dom)
                print("Resolved selector:", json.dumps(resolved, indent=2))
                turn_record["resolved_selector"] = resolved
                selector = resolved["selector"]

                if action["action"] == "type":
                    page.fill(selector, action["value"])
                elif action["action"] == "click":
                    page.click(selector)
                elif action["action"] == "select":
                    # Native <select> dropdowns can't be clicked/filled - this
                    # is the exact gap the eval suite found. select_option()
                    # is the only API that actually works here, matching by
                    # the option's visible text (label), which is what the
                    # brain is instructed to put in 'value'.
                    page.select_option(selector, label=action["value"])
                elif action["action"] == "assert":
                    # Was a no-op before - the agent could say "verified"
                    # without anything real backing it up, which is exactly
                    # what Reflection caught twice (Case 2 and Case 3): a
                    # declared success with no independent evidence behind
                    # it. Now it actually checks the live element's real
                    # text against what the agent expected to see.
                    actual_text = page.locator(selector).text_content() or ""
                    if action.get("value") and action["value"] not in actual_text:
                        raise Exception(
                            f"Assertion failed: expected '{action['value']}' in element, "
                            f"but got '{actual_text.strip()}'"
                        )

                page.wait_for_timeout(3000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Action '{action['action']}' performed on '{selector}'. Proceeding to observe the resulting page."
                })

            except Exception as e:
                print(f"Action failed: {e}")
                turn_record["error"] = str(e)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Action failed with error: {e}. This did not work - "
                               f"reconsider the approach next turn rather than repeating it."
                })
                trail.append(turn_record)
                continue

            trail.append(turn_record)
        else:
            verdict = "inconclusive"

        reflection = reflect_on_trail(goal, trail, verdict)

        browser.close()

    return {
        "goal": goal,
        "start_url": start_url,
        "verdict": verdict,
        "reflection": reflection,
        "trail": trail,
        "turns_used": len(trail)
    }


# Allows running this file directly for a quick single manual check, same
# shape as Days 4-7, but now via the reusable function instead of a
# hardcoded script.
if __name__ == "__main__":
    result = run_agent(
        goal="Log in with valid credentials and verify successful login",
        start_url="https://rahulshettyacademy.com/loginpagePractise/"
    )
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2))