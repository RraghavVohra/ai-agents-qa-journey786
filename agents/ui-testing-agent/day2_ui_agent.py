import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Same goal as Day 1 - nothing changes there. What's different is WHERE
# we are in the flow. Username is already filled in this snapshot, so a
# reasoning agent should notice that and move to password instead.
GOAL = "Log in with valid credentials and verify successful login"

with open("dom_snapshot_step2.html", "r", encoding="utf-8") as f:
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