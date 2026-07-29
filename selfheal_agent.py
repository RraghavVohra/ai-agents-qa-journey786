"""
PROJECT 2 — Self-Healing Locators
Script 1: Prove the core mechanic works

The question today: if a locator breaks, can the model find the right
replacement just by looking at the REAL current page HTML? Nothing
automated yet — no retry loop, no auto-editing test files. Just: does
the reasoning actually work.

Today's story, step by step:
  1. Load the real HTML we captured earlier (dom_snapshot.html)
  2. Describe what we're looking for ("the username input field") and
     the broken selector we tried ("#usernme" — pretend a dev renamed it)
  3. Ask the model, via tool calling, to propose the correct selector
     based on the ACTUAL html — not a guess, an inspection.
  4. Compare its answer to the real one (#username) to check if it
     actually reasoned correctly, or just made something up.
"""

import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()


# ── STEP 1: Load the real page HTML we captured ─────────────────────
with open("dom_snapshot.html", "r", encoding="utf-8") as f:
    page_html = f.read()

# Safety cap: if a page's HTML is huge, we don't want to blow past the
# model's context window. This page is small, but this habit matters
# once you point this at bigger real pages later.
MAX_HTML_CHARS = 15000
if len(page_html) > MAX_HTML_CHARS:
    page_html = page_html[:MAX_HTML_CHARS]


# ── STEP 2: Define the "broken" scenario ─────────────────────────────
broken_selector = "#usernme"  # pretend this is what our old test used
element_intent = "the username input field where the user types their login username"


# ── STEP 3: Define the tool — same pattern as Project 1's tool ──────
tools = [
    {
        "type": "function",
        "function": {
            "name": "propose_fixed_locator",
            "description": "Propose a corrected CSS selector for a broken Playwright locator, based on real page HTML.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fixed_selector": {
                        "type": "string",
                        "description": "The corrected CSS selector that actually exists in the given HTML"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of why this element matches the intended one"
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "How confident the match is"
                    }
                },
                "required": ["fixed_selector", "reasoning", "confidence"]
            }
        }
    }
]

messages = [
    {
        "role": "system",
        "content": (
            "You are a self-healing test automation agent. A Playwright "
            "locator that used to work has stopped matching any element. "
            "You will be given: the broken selector, a description of the "
            "element's intended purpose, and the CURRENT real HTML of the "
            "page. Inspect the HTML carefully and propose the correct "
            "selector for the described element. Always respond using the "
            "propose_fixed_locator tool."
        )
    },
    {
        "role": "user",
        "content": (
            f"Broken selector: {broken_selector}\n"
            f"Element intent: {element_intent}\n\n"
            f"Current page HTML:\n{page_html}"
        )
    }
]


# ── STEP 4: Call the model and read its proposal ─────────────────────
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

message = response.choices[0].message

if message.tool_calls:
    call = message.tool_calls[0]
    result = json.loads(call.function.arguments)
    print("\n🔧 Model proposed a fix:")
    print(json.dumps(result, indent=2))
    print(f"\n✅ Sanity check — does this match reality? Expected: #username")
else:
    print("Model replied in plain text instead of calling the tool:")
    print(message.content)