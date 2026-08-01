import os
import json
from playwright.sync_api import sync_playwright
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Same goal as Days 1-3, still unchanged. Today the difference isn't the
# goal or the prompt - it's WHERE the HTML comes from. Days 1-3 read a
# saved .html file off disk. Today, for the first time, "current page
# HTML" means whatever a real, live browser is actually showing right now.
GOAL = "Log in with valid credentials and verify successful login"
LOGIN_URL = "https://rahulshettyacademy.com/loginpagePractise/"

# --- Brain: same decision mechanic as Days 1-3, untouched -------------------
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
    "If the goal already looks achieved from the current page, return action 'done'."
)

def decide_next_action(goal, dom_html):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": decide_system_prompt},
            {"role": "user", "content": f"Goal: {goal}\n\nCurrent page HTML:\n{dom_html}"}
        ],
        tools=decide_tools,
        tool_choice={"type": "function", "function": {"name": "perform_next_action"}}
    )
    return json.loads(response.choices[0].message.tool_calls[0].function.arguments)


# --- Hands: the missing piece from Days 1-3 ---------------------------------
# The brain only ever produces a plain-English description like "the
# username input field". Playwright needs an actual selector to click or
# fill. This is the EXACT problem the self-healing agent already solved
# (broken selector + intent + real HTML -> correct selector), so instead
# of inventing a new mechanic, we reuse the same shape here: intent + real
# HTML in, one working selector out.
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


# --- The actual loop closing, for the first time, just once -----------------
with sync_playwright() as p:
    # headless=False on purpose - same instinct as verifying in headed/UI
    # mode back in Project 1. You want to SEE the agent's decision actually
    # land on a real page, not just trust a print statement.
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(LOGIN_URL)

    # Step 1 - OBSERVE: read the real, live DOM. Not a snapshot file.
    live_dom = page.content()

    # Step 2 - DECIDE: same brain as Days 1-3, seeing a real page for the
    # first time instead of a rehearsal.
    action = decide_next_action(GOAL, live_dom)
    print("Decided action:")
    print(json.dumps(action, indent=2))

    if action["action"] == "done":
        print("Agent believes the goal is already achieved.")
    else:
        # Step 3 - RESOLVE: turn the plain-English target into a real
        # selector, reusing the self-healing agent's skill.
        resolved = resolve_selector(action["target_description"], live_dom)
        print("Resolved selector:")
        print(json.dumps(resolved, indent=2))

        selector = resolved["selector"]

        # Step 4 - ACT: for the first time, actually DO the thing on a real
        # browser, instead of just printing what should happen.
        if action["action"] == "type":
            page.fill(selector, action["value"])
        elif action["action"] == "click":
            page.click(selector)

        # Step 5 - OBSERVE (again): capture what really happened. Note we
        # read input_value() directly instead of diffing raw page.content() -
        # filling a field updates it live in the browser, but the raw HTML
        # source still shows the old attribute. Raw HTML diffing would make
        # the agent think nothing happened and re-type forever - reading
        # the live value is what actually closes the loop correctly.
        if action["action"] == "type":
            current_value = page.locator(selector).input_value()
            print(f"Field now contains: {current_value}")
        new_dom = page.content()

    input("Press Enter to close the browser...")
    browser.close()