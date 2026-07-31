import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Same goal, unchanged - the agent has no idea "Day 3" exists. All it
# knows is the goal text and whatever page we hand it. If the goal
# genuinely reads as achieved from THIS page, it should say so - not
# because we told it to, but because it looked and decided.
GOAL = "Log in with valid credentials and verify successful login"

# This snapshot is deliberately different in kind, not just degree - Day 2's
# snapshot was "mid-flow" (some fields filled). This one is "post-flow"
# (no login form left at all, a welcome message instead). If the agent
# is really reading the DOM instead of just chasing "which field is
# still empty", this is the page where that habit would break - there
# ARE no fields left to chase.
with open("dom_snapshot_step3.html", "r", encoding="utf-8") as f:
    dom_snapshot = f.read()

tools = [{
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

# Same system prompt as Day 2 - not rewritten for this case. If "done"
# only shows up because we added a special instruction just for it, we
# haven't actually proven the agent recognizes success on its own; we've
# just told it the answer. The rule was already there from Day 1: "if the
# goal already looks achieved from the current page, return action done."
# Today is just the first time that rule actually gets to fire for real.
system_prompt = (
    "You are a UI testing agent. Given a goal and the current page HTML, "
    "decide only the SINGLE next action toward that goal - never plan ahead. "
    "Pay attention to any fields that already have a value filled in - "
    "don't repeat an action that's already been done. "
    "If the goal already looks achieved from the current page, return action 'done'."
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Goal: {GOAL}\n\nCurrent page HTML:\n{dom_snapshot}"}
    ],
    tools=tools,
    tool_choice={"type": "function", "function": {"name": "perform_next_action"}}
)

action = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
print(json.dumps(action, indent=2))