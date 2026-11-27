"""View: CLAUDE.md, a short pointer so Claude Code reads AI_CONTEXT.md first."""
from __future__ import annotations

from .learned_md import RULE

FILE = "CLAUDE.md"

TEXT = """# CLAUDE.md

Read **[AI_CONTEXT.md](AI_CONTEXT.md) first**: the components, what each one owns, how they talk and where to look for X.
Only search the code when it does not answer the question.

- Component diagram: [docs/architecture/components.md](docs/architecture/components.md)
- Architecture decisions: [DECISIONS.md](DECISIONS.md) → `docs/decisions/`
- Facts found in the code later: [LEARNED.md](LEARNED.md)
""" + RULE
