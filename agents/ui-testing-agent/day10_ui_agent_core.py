"""
day10_ui_agent_core.py
(pair files: day10_tasks.py | day10_ui_agent_runner.py)

=============================================================================
THEORY - THE FULL STORY, DAYS 1-10
=============================================================================
  Day 1-3: the BRAIN alone - correct first action, adapts mid-flow,
           recognizes when done. No browser touched yet.
  Day 4:   real browser, one full decide->resolve->act->observe cycle.
  Day 5:   wrapped into an actual repeating loop until done/fail.
  Day 6:   ReAct memory - one growing conversation, so the agent notices
           and recovers from its own mistakes mid-task.
  Day 7:   Reflection - a second review pass catching unresolved failures
           hiding behind a declared "pass".
  Day 8:   Generalization - parameterized into run_agent(goal, url), an
           eval suite across 3 different scenarios, a real gap found
           (native <select> dropdowns) and fixed, 'assert' made to do a
           REAL check instead of being a no-op.
  Day 9:   Credential handling - username/password as real parameters the
           agent must obey, instead of reading them off the page (which a
           real login never displays).
  Day 10:  THIS FILE. Testing a real, live business microsite - not a
           practice page - with a real person (you) who already knows
           exactly what needs checking. That changes what "done" means.

THE ARCHITECTURAL SHIFT - HUMAN-IN-THE-LOOP: Days 1-9 ended with the agent
DECLARING a verdict (pass/fail) via Reflection. That's the agent making a
judgment call. Day 10 removes that authority. The agent's job now ends at
EVIDENCE:
  - what it actually did (the trail, unchanged from Day 6 onward)
  - what it directly OBSERVED via real 'assert' checks against page state
    (Day 8's fix - already produces real, checkable pass/fail-of-a-check
    data, which is different from the AGENT deciding the whole TASK's
    outcome)
  - anything it could not verify or that looked ambiguous

NO pass/fail label comes from the AI anymore. A human reads the evidence
and makes the actual call - this file structurally cannot produce a
verdict, on purpose, not just by convention.

WHAT'S THE SAME AS DAY 9: the decide->resolve->act->observe loop, ReAct
memory, get_live_dom's value/checked/selected syncing, credential
handling. None of that changes - it's proven, and Day 10 builds on it
rather than replacing it.

WHAT'S DIFFERENT: 
  1. Tasks now carry explicit ACCEPTANCE CRITERIA (what should be true
     afterward), fed into the goal so the agent knows what to 'assert'
     against - real, checkable evidence, not a self-declared conclusion.
  2. reflect_on_trail() (pass/fail judgment) is REPLACED by
     summarize_evidence() (neutral report - actions completed, evidence
     observed, gaps/concerns) - structurally incapable of saying "pass".
  3. run_agent() returns "agent_completion_status" (an OPERATIONAL state:
     completed / blocked / max_turns_reached) instead of "verdict" (a
     QUALITY judgment). This is a deliberate rename, not cosmetic - it
     marks the boundary of what the agent is allowed to decide.

IMPORTANT - NOT LINKED TO DAYS 1-9: standalone file, doesn't import from
any day1-day9 file. day9_ui_agent_core.py stays untouched as history.
=============================================================================
"""

import os
import json
from playwright.sync_api import sync_playwright
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Brain's tool schema - 'done' and 'fail' meanings narrowed -------------
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
                "reasoning": {"type": "string"},
                "assert_type": {
                    "type": "string",
                    "enum": ["element_text", "current_url", "element_class", "image_loaded"],
                    "description": "Only used when action is 'assert'. 'element_text' (default) checks a specific element's visible text. 'current_url' checks the browser's actual current URL. 'element_class' checks whether a specific CSS class is genuinely present in an element's class attribute. 'image_loaded' checks whether an <img> element actually loaded correctly (not broken/404) - use this instead of 'element_text' for images, since images have no text content."
                }
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
    "If ACCEPTANCE CRITERIA is provided in the goal message, your job is to "
    "perform the steps needed and then use 'assert' to genuinely check that "
    "criteria against the real page - this produces real evidence for a "
    "human reviewer. You are NOT deciding whether the task passed or "
    "failed overall - that call belongs to a human reviewing your trail. "
    "Once you have completed the intended steps and checked what you can, "
    "use action 'done' to signal you've finished gathering evidence for "
    "this task - regardless of whether an assert matched or not. Only use "
    "'fail' for a genuine BLOCKING problem where you cannot proceed at all "
    "(e.g. a required element is completely absent, or a technical error "
    "stops all further progress) - not to declare the test itself failed. "
    "If explicit credentials are provided in the goal message, you MUST "
    "use exactly those values for any login - never substitute credentials "
    "you happen to see displayed on the page itself. "
    "If the element to interact with is a dropdown (a native <select> "
    "element), use action 'select' with target_description describing the "
    "dropdown itself and 'value' as the exact visible option text. Do not "
    "click/type on individual <option> elements. "
    "'assert' performs a REAL check against the live page. For "
    "'element_text' (default), target_description should describe the "
    "element whose text you expect to contain something, 'value' should be "
    "that expected text. For anchor-link navigation, redirects, or any "
    "check where the real evidence is WHERE the browser currently is (not "
    "what text is visible), set assert_type to 'current_url' instead - "
    "'value' should be the URL fragment you expect (e.g. '#about'). If "
    "you're trying to confirm a CSS CLASS is present on an element (e.g. "
    "'active', 'intro-scroll'), set assert_type to 'element_class' - "
    "target_description should describe the ELEMENT itself (not the "
    "class), and 'value' should be the class name to check for. Do NOT "
    "check for a class name using 'element_text' - a class is an "
    "attribute, not visible text, and checking it that way gives "
    "unreliable results (it may falsely pass or fail for reasons unrelated "
    "to whether the class is actually present). "
    "To check whether an IMAGE actually loaded (not broken/404), set "
    "assert_type to 'image_loaded' - never use 'element_text' on an <img>, "
    "images have no text content and that check can never succeed. "
    "Note: assert checks now tolerate a selector matching several genuinely "
    "identical elements (common with carousel/slider-cloned content) by "
    "checking the first match - you do NOT need to keep refining a "
    "selector to make it uniquely match exactly one element for a presence "
    "check; a reasonably-scoped selector is enough."
)


# --- Hands: resolve_selector, stateless, unchanged from Day 8 --------------
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
    "element on this exact page. "
    "IMPORTANT: never use ':contains(...)' - it is jQuery syntax, not valid "
    "CSS, and will always fail with a syntax error in a real browser. If you "
    "need to match an element by its text, rely on structural/attribute "
    "selectors instead (tag names, classes, ids, nth-child position) - do "
    "not invent text-matching pseudo-classes."
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


# --- REPLACES reflect_on_trail: neutral evidence, no verdict --------------
# The old reflect_on_trail() could say "pass"/"fail"/"pass_with_notes" - a
# quality judgment. This tool is structurally incapable of that: its schema
# has no verdict field at all, only factual/neutral report fields. That's
# the actual mechanism enforcing Human-in-the-Loop, not just a prompt
# instruction that could be ignored.
evidence_tools = [{
    "type": "function",
    "function": {
        "name": "summarize_evidence",
        "description": "Neutrally summarize what happened during this task run, for a human reviewer to make the final call. Do NOT declare pass/fail/success/failure.",
        "parameters": {
            "type": "object",
            "properties": {
                "actions_completed": {
                    "type": "string",
                    "description": "Plain-language summary of what was actually done, in order."
                },
                "evidence_observed": {
                    "type": "string",
                    "description": "What was directly observed/checked - e.g. assert results, page text, state changes. Factual, not evaluative."
                },
                "gaps_or_concerns": {
                    "type": "string",
                    "description": "Anything that could not be verified, any error encountered, or anything ambiguous a human should look at directly."
                }
            },
            "required": ["actions_completed", "evidence_observed", "gaps_or_concerns"]
        }
    }
}]

evidence_system_prompt = (
    "You are reviewing a completed UI test run's full trail, as a neutral "
    "reporter for a human QA reviewer - not as a judge. Summarize what was "
    "done and what was directly observed. Explicitly do NOT say whether the "
    "task passed or failed, succeeded or failed, worked or didn't work - "
    "that determination belongs entirely to the human reading your report. "
    "If something is ambiguous or unverified, say so plainly rather than "
    "guessing at an outcome."
)

def summarize_evidence(goal, acceptance_criteria, trail):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": evidence_system_prompt},
            {"role": "user", "content": (
                f"Goal: {goal}\n\n"
                f"Acceptance criteria: {acceptance_criteria}\n\n"
                f"Full trail:\n{json.dumps(trail, indent=2)}"
            )}
        ],
        tools=evidence_tools,
        tool_choice={"type": "function", "function": {"name": "summarize_evidence"}}
    )
    return json.loads(response.choices[0].message.tool_calls[0].function.arguments)


# --- Observation: unchanged from Day 8/9 ------------------------------------
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


# --- The reusable engine, Human-in-the-Loop ending --------------------------
def run_agent(goal, start_url, acceptance_criteria=None, username=None,
              password=None, max_turns=8, headless=False, browser=None,
              context=None, page=None):
    """
    Runs the decide->resolve->act->observe loop with ReAct memory (Day 6).
    Ends with neutral evidence (Day 10), NOT a pass/fail verdict.

    browser/context/page: optional existing Playwright objects to reuse.
    Pass a shared 'page' in and this function reuses that EXACT tab -
    genuinely one window, one tab, task after task - instead of opening a
    new tab per task. It still starts each task clean via page.goto(),
    which forces a real reload regardless of what a previous task left
    behind. If page isn't provided but context/browser are, falls back to
    opening one new tab in the shared context. If nothing is provided,
    launches and closes everything itself (a plain standalone run).

    Returns a dict:
    {
        goal, start_url, acceptance_criteria,
        agent_completion_status,   # OPERATIONAL only: completed / blocked / max_turns_reached
        evidence,                  # {actions_completed, evidence_observed, gaps_or_concerns}
        trail, turns_used
    }
    """
    credential_note = ""
    if username is not None or password is not None:
        credential_note = (
            f"\n\nUse EXACTLY these credentials for any login on this page: "
            f"username='{username}', password='{password}'. Do NOT use any "
            f"other username or password, even if the page displays other "
            f"valid-looking examples."
        )

    criteria_note = ""
    if acceptance_criteria:
        criteria_note = f"\n\nACCEPTANCE CRITERIA to check via 'assert': {acceptance_criteria}"

    messages = [
        {"role": "system", "content": decide_system_prompt},
        {"role": "user", "content": f"Goal: {goal}{credential_note}{criteria_note}"}
    ]

    trail = []
    agent_completion_status = "max_turns_reached"

    owns_browser = browser is None
    owns_context = context is None
    owns_page = page is None
    playwright_cm = None
    if owns_browser:
        playwright_cm = sync_playwright().start()
        browser = playwright_cm.chromium.launch(headless=headless)
    if owns_context:
        context = browser.new_context()
    if owns_page:
        page = context.new_page()

    # Always navigate fresh - whether this is a brand-new tab or the same
    # reused one, this forces a real reload so each task starts clean.
    page.goto(start_url)
    # Tracks WHERE in messages the current DOM snapshot lives, so it can be
    # replaced (not endlessly appended) each turn. This is the real fix for
    # a real crash: without this, every turn adds ANOTHER full page dump on
    # top of all previous ones - 7 turns means 7 stacked page snapshots in
    # context, which is what blew past the 128k token limit. ReAct's actual
    # memory value is the compact action/outcome history, not repeated full
    # pages - only the CURRENT page needs to be present, not every past one.
    last_dom_message_index = None

    try:
        for turn in range(1, max_turns + 1):
            print(f"\n--- Turn {turn} ---")

            live_dom = get_live_dom(page)
            current_url = page.url

            # Remove the PREVIOUS turn's full page snapshot before adding
            # this turn's - keeps exactly one DOM snapshot in context,
            # ever, no matter how many turns this task takes.
            if last_dom_message_index is not None:
                del messages[last_dom_message_index]

            messages.append({
                "role": "user",
                "content": f"Current URL: {current_url}\n\nCurrent page HTML:\n{live_dom}"
            })
            last_dom_message_index = len(messages) - 1

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
                    "content": "Agent finished gathering evidence for this task."
                })
                agent_completion_status = "completed"
                trail.append(turn_record)
                break

            if action["action"] == "fail":
                # Operational blocker, not a QA verdict - e.g. genuinely
                # cannot locate something required to proceed at all.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "Agent reports it cannot proceed further (blocking issue)."
                })
                agent_completion_status = "blocked"
                trail.append(turn_record)
                break

            try:
                assert_type = action.get("assert_type", "element_text")

                if action["action"] == "assert" and assert_type == "current_url":
                    # URL checks need no selector at all - the evidence is
                    # the browser's own location, not any element on the
                    # page. This is the actual fix: forcing a URL check
                    # through resolve_selector was the root cause of the
                    # nav-home confusion (asking for a selector to match a
                    # full URL against, which no element's text ever would).
                    actual_url = page.url
                    turn_record["checked_url"] = actual_url
                    if action.get("value") and action["value"] not in actual_url:
                        raise Exception(
                            f"URL assertion did not match: expected '{action['value']}' "
                            f"in current URL, but got '{actual_url}'"
                        )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Checked current URL: '{actual_url}'."
                    })

                else:
                    resolved = resolve_selector(action["target_description"], live_dom)
                    print("Resolved selector:", json.dumps(resolved, indent=2))
                    turn_record["resolved_selector"] = resolved
                    selector = resolved["selector"]

                    if action["action"] == "type":
                        page.fill(selector, action["value"])
                    elif action["action"] == "click":
                        page.click(selector)
                    elif action["action"] == "select":
                        page.select_option(selector, label=action["value"])
                    elif action["action"] == "assert" and assert_type == "element_class":
                        # .first is deliberate and safe here (read-only check,
                        # not an interaction) - carousel/slider libraries
                        # commonly clone slide DOM for seamless looping, so a
                        # correct selector can still legitimately match
                        # several genuinely-identical elements. Forcing
                        # uniqueness for a presence check wastes turns
                        # chasing a selector that doesn't need to exist.
                        actual_classes = (page.locator(selector).first.get_attribute("class") or "").split()
                        turn_record["checked_classes"] = actual_classes
                        if action.get("value") and action["value"] not in actual_classes:
                            raise Exception(
                                f"Class assertion did not match: expected class "
                                f"'{action['value']}' on element, but element's "
                                f"actual classes were {actual_classes}"
                            )
                    elif action["action"] == "assert" and assert_type == "image_loaded":
                        # The real, correct check for a broken/404 image - a
                        # failed image request still 'completes' loading, it
                        # just never gets real pixel dimensions. Checking
                        # text_content() on an <img> was never going to work;
                        # images have no text.
                        is_loaded = page.locator(selector).first.evaluate(
                            "el => el.complete && el.naturalWidth > 0"
                        )
                        turn_record["image_loaded"] = is_loaded
                        if not is_loaded:
                            raise Exception(
                                "Image did not load correctly - element matched, "
                                "but naturalWidth is 0 or loading never completed "
                                "(this is the real signature of a broken/404 image)"
                            )
                    elif action["action"] == "assert":
                        actual_text = page.locator(selector).first.text_content() or ""
                        if action.get("value") and action["value"] not in actual_text:
                            raise Exception(
                                f"Assertion did not match: expected '{action['value']}' "
                                f"in element, but got '{actual_text.strip()}'"
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

        # Neutral evidence summary - replaces reflect_on_trail entirely.
        evidence = summarize_evidence(goal, acceptance_criteria, trail)

    finally:
        # Only close the tab if THIS call created it - if a batch runner
        # is reusing one shared tab across tasks, leave it open.
        if owns_page:
            page.close()
        if owns_context:
            context.close()
        if owns_browser:
            browser.close()
            playwright_cm.stop()

    return {
        "goal": goal,
        "start_url": start_url,
        "acceptance_criteria": acceptance_criteria,
        "agent_completion_status": agent_completion_status,
        "evidence": evidence,
        "trail": trail,
        "turns_used": len(trail)
    }