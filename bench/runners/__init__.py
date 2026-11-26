"""Runners answer one question inside one arm's working copy and return the same row shape.

Row: answer, input_tokens, cache_read, cache_write, output_tokens, turns, secs, cost_usd, error.
Compare arms only WITHIN one runner + model: the harnesses differ (Claude Code has its own tools and prompt).
"""
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


def cost(usage: dict, price: dict | None) -> float | None:
    if not price:
        return None
    return (usage.get("input_tokens", 0) * price["input"] + usage.get("output_tokens", 0) * price["output"]
            + usage.get("cache_read", 0) * price.get("cache_read", price["input"])
            + usage.get("cache_write", 0) * price.get("cache_write", price["input"])) / 1e6


def get(runner: str):
    if runner == "anthropic":
        from . import anthropic_api as m
    elif runner == "openai":
        from . import openai_api as m
    elif runner == "claude_code":
        from . import claude_code as m
    elif runner == "fake":
        from . import fake as m
    else:
        raise ValueError(f"unknown runner {runner}")
    return m.run
