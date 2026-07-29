"""
DAY 1 — Teaching an LLM to use a "tool" instead of just talking

Think of this like Playwright: normally you send direct commands
(click, type, wait). Here, instead of commands, we hand the LLM a
MENU of tools it's allowed to use. We ask it something, and if it
decides a tool is the right way to answer, it says "call this tool
with these arguments" instead of writing a paragraph back to us.

Today's story, step by step:
  1. We define ONE tool: generate_test_case
  2. We give the model a user story ("As a user I want to log in...")
  3. Model reads it and decides: "I should call generate_test_case"
  4. We catch that tool call and print the structured result
     — no free-form text, just clean data we can use later.

That's it for today. One tool, one story, one structured output.
Small and complete > big and half-finished.
"""

import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # reads the .env file and loads OPENAI_API_KEY into the environment

client = OpenAI()  # automatically picks up OPENAI_API_KEY that load_dotenv() just loaded


# ── STEP 1: Define the tool ────────────────────────────────────────
# This is a contract: "if you want to give me a test case, give me
# exactly these fields, in this shape." The model can't freelance
# outside this structure.
tools = [
    {
        "type": "function",
        "function": {
            "name": "generate_test_case",
            "description": "Generate a structured test case from a user story.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the test case"
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of test steps"
                    },
                    "expected_result": {
                        "type": "string",
                        "description": "What should happen if the test passes"
                    }
                },
                "required": ["title", "steps", "expected_result"]
            }
        }
    }
]


# ── STEP 2: Give the model a real user story ───────────────────────
user_story = (
    "As a user, I want to log in with valid credentials "
    "so that I can access my dashboard."
)

messages = [
    {
        "role": "system",
        "content": (
            "You are a QA assistant. When given a user story, always use "
            "the generate_test_case tool to respond — never answer in "
            "plain text."
        )
    },
    {
        "role": "user",
        "content": user_story
    }
]


# ── STEP 3: Send it to the model, telling it the tool exists ───────
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
    tool_choice="auto"  # let the model decide whether to use the tool
)


# ── STEP 4: Read the model's decision ──────────────────────────────
# Notice: message.content will likely be EMPTY. The model isn't
# "chatting" — it's calling a function. That's the whole shift from
# chatbot to agent, happening in this one response.
message = response.choices[0].message

if message.tool_calls:
    for call in message.tool_calls:
        print(f"\n🔧 Model chose to call: {call.function.name}")
        print("📦 With these arguments:")
        args = json.loads(call.function.arguments)
        print(json.dumps(args, indent=2))
else:
    print("Model replied in plain text instead of calling the tool:")
    print(message.content)


# ── Run this today ──────────────────────────────────────────────────
# 1. pip install openai python-dotenv
# 2. Create a .env file in this same folder with one line:
#    OPENAI_API_KEY=your-key-here
# 3. Make sure .env and venv/ are listed in your .gitignore
# 4. python day1_agent.py
#
# Expected: a printed JSON block with title, steps, expected_result.
# That JSON is tomorrow's raw material for Day 3 (turning it into a
# real Playwright test file).