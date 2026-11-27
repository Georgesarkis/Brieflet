"""JudgeClient: Claude Code on the user's login (free, default) or the Anthropic API (paid, gated by the use case)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

SUBSCRIPTION_STRIP = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY")


class JudgeClients:
    def __init__(self, system: str):
        self.system = system

    def ask(self, judge: dict, text: str) -> tuple[str, dict]:
        """→ (raw reply, usage dict with input/output tokens and cost_usd if known)."""
        if judge.get("runner", "claude_code") == "claude_code":
            return self._claude_code(judge, text)
        return self._anthropic(judge, text)

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

    def _anthropic(self, judge: dict, text: str) -> tuple[str, dict]:
        import anthropic
        resp = anthropic.Anthropic().messages.create(model=judge["model"], max_tokens=4000, system=self.system,
                                                     messages=[{"role": "user", "content": text}])
        out = "".join(b.text for b in resp.content if b.type == "text")
        return out, {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
