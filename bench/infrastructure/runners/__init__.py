"""Runners answer one question inside one arm's working copy and return the same row shape (domain/results.py).

Compare arms only WITHIN one runner + model: the harnesses differ (Claude Code has its own tools and prompt).
"""
from __future__ import annotations

from importlib import import_module

MODULES = {"anthropic": "anthropic_api", "openai": "openai_api", "claude_code": "claude_code", "fake": "fake"}


def runner_for(name: str):
    """RunnerFactory port: runner name from bench.yaml → its run() function (SDKs load only when used)."""
    if name not in MODULES:
        raise ValueError(f"unknown runner {name}")
    return import_module(f"{__name__}.{MODULES[name]}").run
