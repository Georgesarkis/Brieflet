"""View: LEARNED.md, plus the CLAUDE.md rule that tells assistants to add to it."""
from __future__ import annotations

from ...domain.learned import FILE, LearnedFact

HEADER = """# Learned

Facts an AI assistant had to find in the code because [AI_CONTEXT.md](AI_CONTEXT.md) didn't have them.
One line each: fact → `path`. Brieflet drops lines whose path no longer exists.

"""

RULE = f"""
**When the docs were not enough:** if you had to search the code to answer, add ONE line per missing fact to
[{FILE}]({FILE}): `- <fact, max 25 words> → \\`path/to/file\\``. Check {FILE} before searching the code.
"""


def render(facts: list[LearnedFact]) -> str:
    rows = [f"- {f.fact} → `{f.path}`" + (f" {f.rest}" if f.rest else "") for f in facts]
    return HEADER + ("\n".join(rows) if rows else "_(nothing yet)_") + "\n"
