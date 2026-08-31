"""
analyst.py -- Step 3 of the Data-Analysis Agent

Job of this file: take ONE hypothesis (from the Explorer) and actually
test it against the real data. This is the riskiest component in the
whole agent, because the code that runs here is written by an LLM --
not by us. Nothing here should be trusted by default.

Two layers of defense before any LLM-written code touches real data:
  1. Static check: reject the code outright if it imports anything
     dangerous (os, sys, subprocess, socket, requests, shutil) or calls
     eval/exec/__import__.
  2. Sandboxed execution: even code that passes the static check runs in
     its own subprocess, with a timeout, a clean environment (no
     inherited API keys), and its own throwaway working directory.

Same "don't trust automated output blindly" instinct as the rest of this
agent -- just applied to code instead of conclusions.
"""

import os
import sys
import ast
import json
import tempfile
import subprocess
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Allowlist, not denylist. A denylist only catches imports we thought to
# block (os, subprocess, etc.) -- it does nothing against something
# harmless-but-unapproved like scipy, which isn't dangerous but also
# isn't installed in the sandbox and isn't what the prompt asked for.
# An allowlist rejects anything outside this set, on principle, before
# it ever reaches execution -- catches both malicious AND merely
# off-prompt code with the same check.
ALLOWED_IMPORTS = {"pandas", "numpy", "json", "scipy"}
BLOCKED_CALLS = {"eval", "exec", "__import__", "compile", "open"}

CODE_GEN_TOOL = {
    "type": "function",
    "function": {
        "name": "write_analysis_code",
        "description": "Write Python code using pandas to test one specific hypothesis against a CSV file.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Complete, self-contained Python code. Must: "
                        "import pandas as pd; load the CSV using "
                        "pd.read_csv(CSV_PATH) where CSV_PATH is already "
                        "defined -- do not redefine it; compute a result "
                        "for the hypothesis; and print(json.dumps(result)) "
                        "as the LAST line, where result is a dict with at "
                        "least a 'summary' key (short string) and a "
                        "'value' key (the computed number/stat). Only use "
                        "pandas, numpy, scipy, and json. No file writes, "
                        "no network calls, no other imports."
                    ),
                }
            },
            "required": ["code"],
        },
    },
}

SYSTEM_PROMPT = """You are the Analyst component of a data-analysis agent.
You are given ONE hypothesis and a dataset profile (not the raw data).
Write Python code to test that specific hypothesis using pandas.

Rules:
- Only use pandas, numpy, scipy, and json. Nothing else.
- Assume a variable CSV_PATH already holds the path to the CSV -- just use pd.read_csv(CSV_PATH).
- Your code's last line must be print(json.dumps(result)), where result is a dict with at least 'summary' and 'value' keys.
- Do not write files, make network calls, or use eval/exec.
- Keep it short and directly focused on testing the one hypothesis given.
"""


def contains_blocked_code(code: str):
    """Static safety check via AST -- runs BEFORE any execution.

    Returns a reason string if the code should be rejected, or None if
    it looks safe enough to proceed to sandboxed execution. This is a
    cheap first filter, not a substitute for the sandbox itself -- both
    layers matter.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"code does not parse: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                if top_level not in ALLOWED_IMPORTS:
                    return f"import not on allowlist: {alias.name}"
        if isinstance(node, ast.ImportFrom):
            top_level = node.module.split(".")[0] if node.module else ""
            if top_level not in ALLOWED_IMPORTS:
                return f"import not on allowlist: {node.module}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALLS:
                return f"blocked call: {node.func.id}()"

    return None


def generate_analysis_code(hypothesis: str, profile: dict, model: str = "gpt-4o") -> str:
    """Ask the LLM to write code for exactly one hypothesis."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"hypothesis": hypothesis, "profile": profile})},
        ],
        tools=[CODE_GEN_TOOL],
        tool_choice={"type": "function", "function": {"name": "write_analysis_code"}},
    )
    tool_call = response.choices[0].message.tool_calls[0]
    return json.loads(tool_call.function.arguments)["code"]


def run_in_sandbox(code: str, csv_path: str, timeout_seconds: int = 45) -> dict:
    """Execute LLM-generated code in an isolated subprocess.

    Defenses applied here:
    - Separate process, not the parent's exec() -- a crash or infinite
      loop in the generated code can't take down the agent itself.
    - Hard timeout -- kills anything that hangs (accidental infinite
      loop, huge computation).
    - Clean environment -- the subprocess does NOT inherit OPENAI_API_KEY
      or anything else from the parent's .env. Generated code has no
      reason to need it, so it doesn't get it.
    - Isolated temp working directory -- if the code tries to write a
      file despite instructions, it lands in a throwaway folder that
      gets deleted right after, not the real project.

    Honest limitation: this is process + timeout + minimal-env isolation,
    not full OS-level sandboxing (no Docker/gVisor container here). Good
    enough to contain an accidental bad script; not a defense against a
    truly adversarial one. Worth flagging to Abhishek as a known
    trade-off, not something to claim as bulletproof.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "analysis_script.py")

        # Resolve to an absolute path BEFORE injecting it. The sandbox
        # subprocess runs with cwd=tmpdir (a different directory), so a
        # relative path like "sample_sales.csv" would silently fail to
        # resolve there even though it works fine in the parent process.
        absolute_csv_path = os.path.abspath(csv_path)

        # CSV_PATH is injected as a literal at the top of the script --
        # the LLM never has to (and isn't asked to) construct a path itself.
        # `json` is also guaranteed here rather than trusted to the LLM's
        # generated code -- the required last line (print(json.dumps(...)))
        # would silently fail with a NameError otherwise if the model ever
        # forgets to import it.
        full_script = f"import json\nCSV_PATH = {absolute_csv_path!r}\n" + code

        with open(script_path, "w") as f:
            f.write(full_script)

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env={"PATH": os.environ.get("PATH", "")},  # deliberately minimal env
            )
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"timed out after {timeout_seconds}s (possible infinite loop)"}

        if proc.returncode != 0:
            return {"success": False, "error": proc.stderr.strip()[-500:]}

        try:
            result = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return {"success": False, "error": f"could not parse output as JSON: {proc.stdout[:300]}"}

        return {"success": True, "result": result}


def analyze_hypothesis(hypothesis: str, profile: dict, csv_path: str) -> dict:
    """Full step-3 pipeline for ONE hypothesis: generate code, check it
    statically, then run it in the sandbox. Returns evidence either way
    -- including WHY something was rejected, never a silent failure."""
    code = generate_analysis_code(hypothesis, profile)

    block_reason = contains_blocked_code(code)
    if block_reason:
        return {
            "hypothesis": hypothesis,
            "code": code,
            "success": False,
            "error": f"rejected before execution: {block_reason}",
        }

    sandbox_result = run_in_sandbox(code, csv_path)
    return {"hypothesis": hypothesis, "code": code, **sandbox_result}


if __name__ == "__main__":
    # Standalone test: reuse Profiler + Explorer (both already proven),
    # then run the Analyst on just the FIRST hypothesis -- one hypothesis
    # only, on purpose, so we can inspect one result closely before
    # looping across all of them (that's step 4).
    if len(sys.argv) != 2:
        print("Usage: python analyst.py <path_to_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]

    from profiler import load_dataset, profile_dataset
    from explorer import generate_hypotheses

    df = load_dataset(csv_path)
    profile = profile_dataset(df)
    hypotheses = generate_hypotheses(profile)

    print(f"Testing hypothesis 1 of {len(hypotheses)}:\n  {hypotheses[0]}\n")

    result = analyze_hypothesis(hypotheses[0], profile, csv_path)
    print(json.dumps(result, indent=2))