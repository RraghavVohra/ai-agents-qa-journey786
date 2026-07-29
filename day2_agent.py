"""
DAY 2 — Proving it generalizes, and saving the output for later

Yesterday we proved the model CAN call a tool correctly for one story.
Today's question: does it still work when we change the story? If it
just got lucky with "login," we need to know that now, not on Day 5.

Today's story, step by step:
  1. Wrap yesterday's single call into a reusable function
  2. Feed it THREE different user stories — login, search, checkout
  3. Instead of just printing, SAVE all three results into
     test_cases.json — because Day 3 needs a file to read from when
     it builds real Playwright test files.

Still small: same one tool, just used three times and saved once.
"""

import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()


# ── Same tool definition as Day 1 — no changes needed ───────────────
tools = [
    {
        "type": "function",
        "function": {
            "name": "generate_test_case",
            "description": "Generate a structured test case from a user story.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short title for the test case"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of test steps"
                    },
                    "expected_result": {"type": "string", "description": "What should happen if the test passes"}
                },
                "required": ["title", "steps", "expected_result"]
            }
        }
    }
]


# ── STEP 1: Turn yesterday's one-off call into a reusable function ──
def generate_test_case_for(user_story: str) -> dict:
    """Send one user story to the model and return the structured test case as a dict."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a QA assistant. When given a user story, always use "
                "the generate_test_case tool to respond — never answer in "
                "plain text."
            )
        },
        {"role": "user", "content": user_story}
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message

    if not message.tool_calls:
        # If the model ever skips the tool, we want to know loudly,
        # not silently return nothing.
        raise ValueError(f"Model didn't call the tool for: {user_story}")

    call = message.tool_calls[0]
    return json.loads(call.function.arguments)


# ── STEP 2: Feed it THREE different stories, not just login ─────────
user_stories = [
    "As a user, I want to log in with valid credentials so that I can access my dashboard.",
    "As a user, I want to search for a product by name so that I can find items I'm interested in.",
    "As a user, I want to add a product to my cart and checkout so that I can complete my purchase."
]

all_test_cases = []

for story in user_stories:
    print(f"\n📝 Story: {story}")
    test_case = generate_test_case_for(story)
    print(json.dumps(test_case, indent=2))
    all_test_cases.append(test_case)


# ── STEP 3: Save everything to a file — this is new vs. Day 1 ───────
# Day 3 will open this exact file to turn each entry into a real
# Playwright .py test file. This is the handoff point between the
# "thinking" part of the agent and the "writing code" part.
with open("test_cases.json", "w") as f:
    json.dump(all_test_cases, f, indent=2)

print(f"\n✅ Saved {len(all_test_cases)} test cases to test_cases.json")