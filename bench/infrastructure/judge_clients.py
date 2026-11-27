"""JudgeClient: a plugin judge, named by the `runner` in bench.yaml's `judge:` block. The use case does the money gate.

A plugin registers `ask(system, judge, text) -> (raw reply, usage)` under the `brieflet.bench_judges` entry point group.
"""
from __future__ import annotations

from importlib.metadata import entry_points

GROUP = "brieflet.bench_judges"


class JudgeClients:
    def __init__(self, system: str):
        self.system = system

    def ask(self, judge: dict, text: str) -> tuple[str, dict]:
        """→ (raw reply, usage dict with input/output tokens and cost_usd if known)."""
        runner = judge.get("runner")
        ep = {e.name: e for e in entry_points(group=GROUP)}.get(runner)
        if ep is None:
            raise ValueError(f"unknown judge runner {runner}")
        return ep.load()(self.system, judge, text)
