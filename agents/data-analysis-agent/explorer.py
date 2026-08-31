"""
explorer.py -- Step 2 of the Data-Analysis Agent

Job of this file, and only this file: look at the Profiler's output and
propose hypotheses worth investigating. It does NOT test them -- that's
the Analyst's job (step 3). Separating "what should we check" from
"let's check it" means a bad hypothesis list can be fixed by fixing this
one prompt, without ever touching execution code.
"""

import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv

from profiler import load_dataset, profile_dataset

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Tool schema: forces the LLM to hand back a clean list of hypotheses,
# instead of free-form text we'd have to parse ourselves. Same
# tool-calling pattern used in the Self-Healing Locator Agent.
HYPOTHESIS_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_hypotheses",
        "description": "Propose data hypotheses worth investigating, based on a dataset profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "hypotheses": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Each item is a single testable question about the "
                        "data, phrased plainly, e.g. 'Do units_sold spike "
                        "on weekends?'"
                    ),
                }
            },
            "required": ["hypotheses"],
        },
    },
}

SYSTEM_PROMPT = """You are the Explorer component of a data-analysis agent.
You are given a JSON profile of a dataset (columns, types, stats) -- never the raw data itself.
Your only job: propose a short list of specific, testable hypotheses worth investigating.

Rules:
- Each hypothesis must be answerable using the columns present in the profile.
- Prefer hypotheses that compare two things (a metric across a category, a metric over time, a relationship between two numeric columns).
- Do not answer the hypotheses. Do not guess results. Only propose the question.
- Propose 3 to 6 hypotheses. Fewer, sharper hypotheses are better than many vague ones.
"""


def extract_hypotheses_from_tool_call(tool_call) -> list[str]:
    """Pulls the hypothesis list out of the API's tool_call response.

    Kept separate from generate_hypotheses() below so this parsing logic
    can be tested on its own with a fake tool_call object -- no live API
    call needed to prove this part works.
    """
    args = json.loads(tool_call.function.arguments)
    return args["hypotheses"]


def generate_hypotheses(profile: dict, model: str = "gpt-4o") -> list[str]:
    """Call the LLM once, with the profile as context, and get back a
    clean list of hypothesis strings via tool-calling."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(profile)},
        ],
        tools=[HYPOTHESIS_TOOL],
        tool_choice={"type": "function", "function": {"name": "propose_hypotheses"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    return extract_hypotheses_from_tool_call(tool_call)


if __name__ == "__main__":
    # Standalone test: reuse the Profiler (already proven), feed its
    # output into the Explorer, and just print what comes back. No
    # execution of any hypothesis happens here -- that's step 3.
    if len(sys.argv) != 2:
        print("Usage: python explorer.py <path_to_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    df = load_dataset(csv_path)
    profile = profile_dataset(df)

    hypotheses = generate_hypotheses(profile)

    print("Hypotheses proposed:\n")
    for i, h in enumerate(hypotheses, start=1):
        print(f"{i}. {h}")