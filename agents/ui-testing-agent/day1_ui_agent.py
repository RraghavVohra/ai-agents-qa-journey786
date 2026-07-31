import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# The goal is plain English - no selectors, no steps. Just what a human
# tester would ask for.
GOAL = "Log in with valid credentials and verify successful login"

# Same DOM snapshot the self-healing agent used - the agent's "eyes"
# are the same skill, just reused here.
with open("dom_snapshot.html", "r", encoding="utf-8") as f:
    dom_snapshot = f.read()

# The contract: model must return ONE action, not a plan. It doesn't know
# what happens after - it'll be shown the new page before deciding again.
tools = [{
    "type": "function",
    "function": {
        "name": "perform_next_action",
        "description": "Decide the single next UI action toward the goal, based only on the current page.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["click", "type", "assert", "done"],
                    "description": "Type of action to take next."
                },
                "target_description": {
                    "type": "string",
                    "description": "Plain-English description of the element, e.g. 'the username input field'. Not a selector."
                },
                "value": {
                    "type": "string",
                    "description": "Text to type, only if action is 'type'."
                },
                "reasoning": {
                    "type": "string",
                    "description": "One sentence: why this action, right now."
                }
            },
            "required": ["action", "target_description", "reasoning"]
        }
    }
}]

system_prompt = (
    "You are a UI testing agent. Given a goal and the current page HTML, "
    "decide only the SINGLE next action toward that goal - never plan ahead. "
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