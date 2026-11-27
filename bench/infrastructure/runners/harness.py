"""What every API runner shares: the system prompt and Claude Code's habit of loading CLAUDE.md."""
from __future__ import annotations

from pathlib import Path

SYSTEM = (
    "You answer questions about the code repository you can see through the tools. "
    "Look in the repository before answering; name the files (and lines where useful) your answer rests on. "
    "When you have enough to answer, stop calling tools and give the answer."
)


def project_instructions(workdir: Path) -> str:
    """Mimic Claude Code: CLAUDE.md (or AGENTS.md) at the repo root is loaded into context automatically."""
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = Path(workdir, name)
        if p.is_file():
            return f"\n\nProject instructions from {name}:\n\n" + p.read_text(encoding="utf-8", errors="replace")
    return ""


def empty_usage() -> dict:
    return {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0}
