import os
import json
from playwright.sync_api import sync_playwright
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

GOAL = "Log in with valid credentials and verify successful login"
LOGIN_URL = "https://rahulshettyacademy.com/loginpagePractise/"

# Safety cap - even WITH memory, a model could still loop. Memory helps it
# notice a mistake; it doesn't guarantee it always will. Same honest safety
# net as Day 5, unchanged.
MAX_TURNS = 6

# --- Brain's tool schema: unchanged from Day 5 ------------------------------
decide_tools = [{
    "type": "function",
    "function": {
        "name": "perform_next_action",
        "description": "Decide the single next UI action toward the goal, based on the current page and everything tried so far.",
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

# Slightly updated from Day 5 - now explicitly tells the model that its own
# past turns are visible to it in this same conversation, and that it should
# actually use that history rather than re-deciding from scratch each time.
decide_system_prompt = (
    "You are a UI testing agent working toward a single goal. You will see "
    "the full history of your own past Thoughts, Actions, and their real "
    "Observations in this conversation - use that history. If a past action "
    "did not produce the expected change, do not simply repeat it - reason "
    "about why and try something different. "
    "Decide only the SINGLE next action toward the goal - never plan ahead. "
    "Don't repeat an action whose result you can already see succeeded. "
    "If the goal already looks achieved from the current page, return action "
    "'done'. Real production pages after a successful login don't always "
    "show an explicit 'welcome' message - the URL itself is strong evidence. "
    "If the current URL has changed away from the original login page, and "
    "there is no login form and no error message visible, treat that as "
    "sufficient evidence the goal is already achieved."
)


# --- Hands: resolve_selector stays STATELESS, on purpose --------------------
# Turning "the username field" into a real selector doesn't benefit from
# remembering turn 1 - it only ever needs the CURRENT page. Memory belongs
# to the decision loop, not every function in the pipeline. Reused as-is
# from Day 4/5, the self-healing agent's exact skill.
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


# --- Unchanged sync logic from Day 5, now wrapped with a defensive retry ---
# page.evaluate() can genuinely fail mid-navigation: the moment a new page
# starts loading, the browser destroys the OLD page's JS execution context
# and builds a fresh one. If evaluate() is in flight during that exact
# destruction window, it throws - not because anything is really wrong, just
# unlucky timing. A fixed wait_for_timeout() usually dodges this, but
# "usually" isn't good enough, so we also retry specifically on this error.
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
                # Genuinely mid-navigation - not a real failure, just wait a
                # beat for the new page's context to exist and try again.
                page.wait_for_timeout(retry_delay_ms)
                continue
            raise
    raise last_error


# --- The actual ReAct wiring -------------------------------------------------
# This is the real difference from Day 5. Day 5's decide_next_action() built
# a brand-new 2-message list every single call - system prompt + current
# page, nothing else, every time. Turn 5 had zero idea what turns 1-4 did.
#
# Here, `messages` is built ONCE, before the loop, and every turn APPENDS to
# it instead of replacing it. That's the whole mechanism: each new decision
# is made with the entire trace of past Thoughts, Actions, and real
# Observations still sitting in context - not just "what's true right now".
messages = [
    {"role": "system", "content": decide_system_prompt},
    {"role": "user", "content": f"Goal: {GOAL}"}
]

trail = []
verdict = "inconclusive"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(LOGIN_URL)

    for turn in range(1, MAX_TURNS + 1):
        print(f"\n--- Turn {turn} ---")

        # OBSERVE: same live-DOM mechanic as Day 5. On turn 1, this is the
        # very first thing the agent ever sees; on later turns, it's the
        # real result of whatever the PREVIOUS turn's action just did.
        live_dom = get_live_dom(page)
        current_url = page.url

        # This observation message has nowhere to attach as a tool result
        # yet (nothing's been decided this turn), so it's a plain user
        # message - the "here's what the world looks like right now" input,
        # same shape Day 1-5 always used, just appended instead of standalone.
        messages.append({
            "role": "user",
            "content": f"Current URL: {current_url}\n\nCurrent page HTML:\n{live_dom}"
        })

        # DECIDE: the call itself looks almost identical to Day 5's - same
        # tools, same forced tool_choice. The only real difference is we
        # pass the FULL growing `messages` list instead of a fresh 2-message
        # one. That's it. That's the entire ReAct upgrade, mechanically.
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

        # The assistant's own Thought+Action must be appended EXACTLY as the
        # API returned it (same tool_call id), so the Observation we add
        # next can correctly reference it - this is what keeps the
        # conversation validly threaded turn over turn.
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
            # Close out the tool-call contract even on the finishing turn,
            # then stop - same "done" mechanic proven back on Day 3, now
            # happening with full history behind it instead of in isolation.
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": "Agent concluded the goal is achieved. No action taken."
            })
            verdict = "pass"
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
            elif action["action"] == "assert":
                pass

            # Settle wait - a generous FIXED buffer as the PRIMARY safety
            # net, learned the hard way: this site's Sign In flow uses a
            # plain client-side setTimeout(2000ms) before doing anything -
            # no network request fires during that wait, so
            # wait_for_load_state("networkidle") returns almost instantly
            # and is completely blind to it. It only detects NETWORK
            # activity, not a JS timer quietly sitting in the same page. A
            # too-short wait here made the agent observe the page mid
            # "Signing.." state and hallucinate a wrong diagnosis (a modal
            # it thought was blocking it, which was actually just an
            # always-present-but-hidden element from an unrelated feature).
            # Fixed wait first, load-state check second as a harmless
            # best-effort extra for genuinely network-driven redirects.
            page.wait_for_timeout(3000)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            # The OBSERVATION - this is the actual new ingredient. Instead of
            # just moving on to next turn's fresh DOM read, we explicitly
            # tell the model, as a real tool result, what it just did and
            # that it happened. The NEXT turn's loop iteration will still
            # append the fresh live DOM as before - this tool message just
            # satisfies the API's contract (a tool_call must be followed by
            # a tool result) and gives the model an explicit "yes, that
            # action ran" confirmation in its own history.
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
                "content": f"Action failed with error: {e}"
            })
            verdict = "fail"
            trail.append(turn_record)
            break

        trail.append(turn_record)
    else:
        verdict = "inconclusive"

    print("\n=== FINAL VERDICT:", verdict.upper(), "===")
    print("\n=== TRAIL ===")
    print(json.dumps(trail, indent=2))

    input("\nPress Enter to close the browser...")
    browser.close()