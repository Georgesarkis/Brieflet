"""Offline runner for tests and dry rehearsals: no network, no cost. Tokens = size of what the arm puts in front of
the model (CLAUDE.md + the files it points at), so arms differ the way a real run would in direction only."""
from __future__ import annotations

from pathlib import Path

from .harness import project_instructions


def run(question: str, workdir: Path, model: dict, price: dict | None, max_usd_this_run: float) -> dict:
    ctx = project_instructions(workdir)
    n = sum(f.stat().st_size for f in Path(workdir).rglob("*.md") if f.is_file()) // 4 + len(ctx) // 4 + 5000
    return {"input_tokens": 0, "cache_read": n, "cache_write": 0, "output_tokens": 500, "turns": 3, "secs": 0.0,
            "cost_usd": 0.0, "answer": f"[fake] {question[:60]}", "error": None}
