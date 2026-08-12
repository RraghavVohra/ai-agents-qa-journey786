"""
day9_credential_test.py

=============================================================================
THEORY - WHAT THIS FILE PROVES
=============================================================================
Every proof through Day 8 worked because the target page displayed its own
valid credentials in plain text. A real organizational login never will -
so the agent needs to be GIVEN credentials, not discover them.

This alone is easy to fake pass: if we gave it 'standard_user' (the first,
most visually prominent username on saucedemo.com's own displayed list),
we could never tell whether the agent actually used what we gave it, or
just got lucky reading the page.

So this test deliberately uses 'problem_user' instead - a valid account,
but NOT the first/most obvious one listed on the page. If the agent's
typed username in the trail is 'problem_user', that's real proof it obeyed
the given credentials. If it's 'standard_user' instead, that proves it's
still defaulting to reading the page - the actual bug this fix needs to
have closed.
=============================================================================
"""

import json
from day9_ui_agent_core import run_agent

GIVEN_USERNAME = "problem_user"
GIVEN_PASSWORD = "secret_sauce"

result = run_agent(
    goal="Log in and verify successful login",
    start_url="https://www.saucedemo.com/",
    username=GIVEN_USERNAME,
    password=GIVEN_PASSWORD
)

print("\n=== RESULT ===")
print(json.dumps(result, indent=2))

# --- The actual check -------------------------------------------------------
typed_values = [
    turn["decision"].get("value", "")
    for turn in result["trail"]
    if turn["decision"]["action"] == "type"
]

print("\n=== CREDENTIAL CHECK ===")
print(f"Given username : {GIVEN_USERNAME}")
print(f"Typed values   : {typed_values}")

if GIVEN_USERNAME in typed_values:
    print("PASS - agent used the given username, not a page-displayed default.")
else:
    print("FAIL - agent did not use the given username. Check the credential "
          "override logic in day8_ui_agent_core.py.")