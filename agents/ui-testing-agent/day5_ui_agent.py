import os
import json
from playwright.sync_api import sync_playwright
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

GOAL = "Log in with valid credentials and verify successful login"
LOGIN_URL = "https://rahulshettyacademy.com/loginpagePractise/"

# Safety cap - an LLM deciding "what's next" in a loop could, in theory,
# never say "done". Rather than trust that it always will, we bound the
# number of turns. Hitting this without finishing is reported honestly as
# inconclusive, not silently retried forever.
MAX_TURNS = 6

# --- Brain: identical to Days 1-4, untouched --------------------------------
decide_tools = [{
    "type": "function",
    "function": {
        "name": "perform_next_action",
        "description": "Decide the single next UI action toward the goal, based only on the current page.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "type", "assert", "done"]},
                "target_description": {"type": "string"},
                "value": {"type": "string"},
                "reasoning": {"type": "string"}
            },
            "required": ["action", "target_description", "reasoning"]
        }
    }
}]

decide_system_prompt = (
    "You are a UI testing agent. Given a goal and the current page HTML, "
    "decide only the SINGLE next action toward that goal - never plan ahead. "
    "Pay attention to any fields that already have a value filled in - "
    "don't repeat an action that's already been done. "
    "If the goal already looks achieved from the current page, return action 'done'. "
    "Real production pages after a successful login don't always show an "
    "explicit 'welcome' message - the URL itself is strong evidence. If the "
    "current URL has changed away from the original login page, and there is "
    "no login form and no error message visible, treat that as sufficient "
    "evidence the goal is already achieved."
)

def decide_next_action(goal, dom_html, current_url):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": decide_system_prompt},
            {"role": "user", "content": f"Goal: {goal}\n\nCurrent URL: {current_url}\n\nCurrent page HTML:\n{dom_html}"}
        ],
        tools=decide_tools,
        tool_choice={"type": "function", "function": {"name": "perform_next_action"}}
    )
    return json.loads(response.choices[0].message.tool_calls[0].function.arguments)


# --- Hands: identical to Day 4, untouched -----------------------------------
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


# --- The fix: page.content() lies about live input state --------------------
# page.content() returns the page's ORIGINAL server-rendered HTML source.
# When Playwright fills a field, the browser updates that field's live
# "value" PROPERTY - but the raw HTML "value" ATTRIBUTE never changes to
# match. Day 4's print statement worked around this by reading
# input_value() directly for display, but the actual OBSERVE step that
# feeds the brain was still using page.content() underneath - so the brain
# was always looking at a page that still claimed the username field was
# empty, turn after turn, no matter how many times it had already been
# filled. This is what caused the Turn 1-6 loop: the agent wasn't being
# dumb, it was reasoning correctly off a stale observation.
#
# Fix: before serializing, sync every input/textarea's live value onto its
# HTML attribute so the brain always sees what's REALLY on the page.
def get_live_dom(page):
    return page.evaluate("""
        () => {
            document.querySelectorAll('input, textarea').forEach(el => {
                if (el.type === 'checkbox' || el.type === 'radio') {
                    // checked state lives in a live PROPERTY too, same as
                    // text value did - the raw 'checked' ATTRIBUTE doesn't
                    // update on its own just because a real click toggled it.
                    if (el.checked) {
                        el.setAttribute('checked', 'checked');
                    } else {
                        el.removeAttribute('checked');
                    }
                } else {
                    el.setAttribute('value', el.value);
                }
            });

            // Real live pages carry megabytes of tracking/analytics script
            // noise (GTM, Facebook pixel, Google Ads, etc.) that our clean
            // static snapshots never had. None of it helps the agent decide
            // anything, but its sheer size can bury a small, meaningful
            // change - like a single 'checked' attribute - deep enough
            // that the model loses track of it. Clone the DOM (so the real
            // live page itself is untouched) and strip that noise before
            // serializing, so the model only ever sees the actual visible,
            // interactive markup.
            const clone = document.documentElement.cloneNode(true);
            clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
            return clone.outerHTML;
        }
    """)


# --- The actual loop, closing for real this time ----------------------------
# trail keeps a record of every turn - what was decided, what selector was
# used, what happened. This isn't just for debugging today; it's the shape
# of the "here's how I tested this and what happened" report the agent is
# meant to produce as its final output, per the original Project 3 goal.
trail = []
verdict = "inconclusive"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(LOGIN_URL)

    for turn in range(1, MAX_TURNS + 1):
        print(f"\n--- Turn {turn} ---")

        # OBSERVE: always the real, live page - never a saved file. Using
        # get_live_dom(), not page.content(), so filled-in values are
        # actually reflected (see the note above resolve_selector for why
        # this matters).
        live_dom = get_live_dom(page)

        # DECIDE: same brain as every prior day, now also given the current
        # URL - the one signal a human tester would glance at instantly to
        # know "we're not on the login page anymore", which the agent had
        # no way to know from HTML alone.
        action = decide_next_action(GOAL, live_dom, page.url)
        print("Decided:", json.dumps(action, indent=2))

        turn_record = {"turn": turn, "decision": action}

        if action["action"] == "done":
            # The agent itself is declaring the goal met, from what it can
            # currently see - same mechanic proven in isolation back on Day 3.
            verdict = "pass"
            trail.append(turn_record)
            break

        try:
            # RESOLVE: plain-English target -> real selector, reusing the
            # self-healing agent's exact skill.
            resolved = resolve_selector(action["target_description"], live_dom)
            print("Resolved selector:", json.dumps(resolved, indent=2))
            turn_record["resolved_selector"] = resolved
            selector = resolved["selector"]

            # ACT: actually do it, for real, on the live browser.
            if action["action"] == "type":
                page.fill(selector, action["value"])
            elif action["action"] == "click":
                page.click(selector)
            elif action["action"] == "assert":
                # Not yet needed by this flow's decisions, but the schema
                # allows it - treat as a no-op observation point rather
                # than crashing if the brain ever picks it.
                pass

            # Settle pause - some actions (like submitting a login form)
            # trigger a delayed redirect on the real site. Observing
            # immediately after acting risks reading a stale page, so we
            # give the browser a moment before the next turn's OBSERVE step.
            page.wait_for_timeout(2500)

        except Exception as e:
            # A selector that doesn't resolve, or an action that fails, is a
            # real test failure - not something to silently retry into an
            # infinite loop.
            print(f"Action failed: {e}")
            turn_record["error"] = str(e)
            verdict = "fail"
            trail.append(turn_record)
            break

        trail.append(turn_record)
    else:
        # Loop exhausted MAX_TURNS without the agent ever saying "done" -
        # reported honestly as inconclusive, not assumed to be a pass.
        verdict = "inconclusive"

    print("\n=== FINAL VERDICT:", verdict.upper(), "===")
    print("\n=== TRAIL ===")
    print(json.dumps(trail, indent=2))

    input("\nPress Enter to close the browser...")
    browser.close()