"""JudgeClient: Claude Code on the user's login (free, default), or a plugin judge (paid, gated by the use case).

A plugin judge registers `ask(system, judge, text) -> (raw reply, usage)` under the `brieflet.bench_judges`
entry point group, named like the `runner` in bench.yaml's `judge:` block.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from importlib.metadata import entry_points

GROUP = "brieflet.bench_judges"
SUBSCRIPTION_STRIP = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY")


class JudgeClients:
    def __init__(self, system: str):
        self.system = system

    def ask(self, judge: dict, text: str) -> tuple[str, dict]:
        """→ (raw reply, usage dict with input/output tokens and cost_usd if known)."""
        runner = judge.get("runner", "claude_code")
        if runner == "claude_code":
            return self._claude_code(judge, text)
        ep = {e.name: e for e in entry_points(group=GROUP)}.get(runner)
        if ep is None:
            raise ValueError(f"unknown judge runner {runner}")
        return ep.load()(self.system, judge, text)

    def _claude_code(self, judge: dict, text: str) -> tuple[str, dict]:
        exe = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
        env = {k: v for k, v in os.environ.items() if k not in SUBSCRIPTION_STRIP}
        p = subprocess.run([exe, "-p", self.system + "\n\n" + text, "--model", judge.get("model", "opus"),
                            "--output-format", "json", "--tools", "", "--strict-mcp-config", "--no-session-persistence"],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600, cwd="/tmp")
        try:
            d = json.loads(p.stdout)
        except ValueError:
            return "", {}
        u = d.get("usage") or {}
        return d.get("result") or "", {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
                                       "cost_usd": d.get("total_cost_usd")}
