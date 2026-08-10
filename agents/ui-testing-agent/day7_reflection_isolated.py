import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

GOAL = "Log in with valid credentials and verify successful login"

# This is the REAL trail from the run where turn 3's checkbox click failed
# (forced, on purpose) and turn 4 silently moved on to Sign In without ever
# retrying or acknowledging it - yet the run still ended in a PASS, because
# the site never actually validates that checkbox. Perfect real test case:
# does Reflection catch this discrepancy, or does it just rubber-stamp the
# original verdict?
ORIGINAL_VERDICT = "pass"
TRAIL = [
    {
        "turn": 1,
        "decision": {
            "action": "type",
            "target_description": "input field for username",
            "value": "rahulshettyacademy",
            "reasoning": "The goal is to log in with valid credentials. The provided page includes a placeholder username 'rahulshettyacademy', suggesting that this is the correct value to use for logging in."
        },
        "resolved_selector": {"selector": "#username", "confidence": "high"}
    },
    {
        "turn": 2,
        "decision": {
            "action": "type",
            "target_description": "input field for password",
            "value": "Learning@830$3mK2",
            "reasoning": "The goal is to log in using the provided credentials. The page suggests 'Learning@830$3mK2' as the correct password for 'rahulshettyacademy', so I will enter this password next."
        },
        "resolved_selector": {"selector": "input[type=\"password\"]", "confidence": "high"}
    },
    {
        "turn": 3,
        "decision": {
            "action": "click",
            "target_description": "checkbox for agreeing to terms and conditions",
            "reasoning": "The terms and conditions checkbox needs to be checked before attempting to log in to ensure the form is completed correctly and can be submitted."
        },
        "resolved_selector": {"selector": "#this-id-does-not-exist", "confidence": "high"},
        "error": "Page.click: Timeout 30000ms exceeded.\nCall log:\n  - waiting for locator(\"#this-id-does-not-exist\")\n"
    },
    {
        "turn": 4,
        "decision": {
            "action": "click",
            "target_description": "Sign In button",
            "reasoning": "Since the username and password have been entered correctly, proceeding to click the 'Sign In' button will attempt to submit the login form."
        },
        "resolved_selector": {"selector": "#signInBtn", "confidence": "high"}
    },
    {
        "turn": 5,
        "decision": {
            "action": "done",
            "target_description": "successful login check",
            "reasoning": "The URL has changed to a different page (https://rahulshettyacademy.com/angularpractice/shop) which indicates that the login was successful as the login form is no longer visible and no error message was displayed."
        }
    }
]

reflect_tools = [{
    "type": "function",
    "function": {
        "name": "reflect_on_trail",
        "description": "Review a completed test run's full trail and give a reflected verdict, noting any discrepancies for a human QA reviewer.",
        "parameters": {
            "type": "object",
            "properties": {
                "reflected_verdict": {
                    "type": "string",
                    "enum": ["pass", "fail", "pass_with_notes"],
                    "description": "pass_with_notes = the stated goal was achieved, but something worth flagging happened along the way."
                },
                "notes": {
                    "type": "string",
                    "description": "Any discrepancy worth a human QA reviewer knowing - e.g. an intended action that failed and was never retried or confirmed, even if the overall goal still succeeded."
                }
            },
            "required": ["reflected_verdict", "notes"]
        }
    }
}]

# The key instruction here: this is NOT "was the final verdict right or
# wrong" - it's "does every intended action in the trail have a clear,
# successful resolution, and if not, say so explicitly." A goal can still
# be genuinely achieved while an intended step quietly never completed -
# that gap is exactly what a human tester would want surfaced, not hidden
# behind a clean-looking PASS.
reflect_system_prompt = (
    "You are reviewing a completed UI test run's full trail of actions, as a "
    "second reviewer - not the agent that ran it. Carefully check: did every "
    "action the agent INTENDED to take actually succeed, or get properly "
    "retried after a failure? Flag any action that failed and was never "
    "revisited by a later turn, even if the overall goal still appears to "
    "have been achieved by other means. Use 'pass_with_notes' when the goal "
    "was genuinely achieved but something in the trail is still worth a "
    "human QA reviewer knowing about."
)

def reflect_on_trail(goal, trail, original_verdict):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": reflect_system_prompt},
            {"role": "user", "content": (
                f"Goal: {goal}\n\n"
                f"Original verdict from the agent that ran this: {original_verdict}\n\n"
                f"Full trail:\n{json.dumps(trail, indent=2)}"
            )}
        ],
        tools=reflect_tools,
        tool_choice={"type": "function", "function": {"name": "reflect_on_trail"}}
    )
    return json.loads(response.choices[0].message.tool_calls[0].function.arguments)


reflection = reflect_on_trail(GOAL, TRAIL, ORIGINAL_VERDICT)
print("=== REFLECTION ===")
print(json.dumps(reflection, indent=2))