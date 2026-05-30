"""System prompt and message templates for lean context-file generation.

Design principles (Session 1 §2 Q3, Session 2 §4.5):
- Output MUST be a LEAN ≤~20-line file.
- Include: real test/build commands, non-obvious conventions, internal APIs.
- EXCLUDE: architecture prose, linter-enforceable rules, directory dumps,
  generic style advice, anything the agent can infer from the code itself.

The generated file is the artifact under test (with_context=True arm).
Its value comes from what isn't obvious; not from restating what is.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

LEAN_SYSTEM_PROMPT = """\
You are a senior engineer writing a minimal context file for an AI coding agent.
The file will be placed in the repo root so the agent reads it automatically.

STRICT RULES — violating any one is a failure:
1. Output ONLY the file contents, no preamble, no explanation, no markdown wrapper.
2. The file MUST be ≤ 20 lines. Every line must earn its place.
3. Include ONLY:
   - The real, runnable test command (e.g. `pytest tests/` or `npm test`)
   - The real, runnable build/lint command if it exists
   - Non-obvious project conventions the agent cannot infer from the code
   - Internal API names or patterns that are tricky or counter-intuitive
4. EXCLUDE everything that is obvious, generic, or linter-enforceable:
   - Do NOT list directory structure
   - Do NOT give architecture overviews
   - Do NOT repeat what is in the README or pyproject.toml
   - Do NOT add style rules (e.g. "use type hints", "follow PEP 8")
   - Do NOT pad with empty advice
5. If you have fewer than 3 genuinely non-obvious things to say, say fewer things.
   A 5-line honest file beats a 20-line padded one.
"""

# ---------------------------------------------------------------------------
# User message template
# ---------------------------------------------------------------------------

def build_user_message(profile_summary: str) -> str:
    """Build the user message from a repo profile summary string."""
    return (
        f"Generate the context file for this repository.\n\n"
        f"Repository profile:\n{profile_summary}"
    )


# ---------------------------------------------------------------------------
# Retry prompt (simplified, used on second attempt after malformed output)
# ---------------------------------------------------------------------------

RETRY_SYSTEM_PROMPT = """\
You are writing a minimal context file for an AI coding agent.
Output ONLY the file contents — nothing else.
Maximum 20 lines. Include only: test command, build command (if any),
non-obvious conventions. Nothing generic.
"""


def build_retry_message(profile_summary: str) -> str:
    """Simplified user message for the retry attempt."""
    return (
        f"Write the context file for this repo. Be extremely concise.\n\n"
        f"Repo info:\n{profile_summary}"
    )
