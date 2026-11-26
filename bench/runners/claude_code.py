"""Claude Code headless (`claude -p`), read-only tools. Same setup as geolinux's 22 Nov dev_token_compare.sh.

billing: subscription (default) strips API keys so it runs on your Claude login: $0 extra, but it uses your plan's
usage limit. cost_usd is what Claude Code reports the same work would cost at API price (for comparison only).
billing: api keeps ANTHROPIC_API_KEY and is real money.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path


def run(question: str, workdir: Path, model: dict, price: dict | None, max_usd_this_run: float) -> dict:
    exe = model.get("claude_bin") or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    env = dict(os.environ)
    if model.get("billing", "subscription") == "subscription":
        for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY"):
            env.pop(k, None)
    cmd = [exe, "-p", question, "--model", model["model"], "--output-format", "json",
           "--tools", "Read,Grep,Glob", "--allowedTools", "Read,Grep,Glob",
           "--disallowedTools", "Bash,Edit,Write,WebFetch,WebSearch",
           "--strict-mcp-config", "--permission-prompts", "none", "--no-session-persistence"]
    if model.get("billing") == "api":
        cmd += ["--max-budget-usd", f"{max_usd_this_run:.2f}"]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=workdir, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       timeout=model.get("timeout_s", 900))
    secs = round(time.time() - t0, 1)
    try:
        d = json.loads(p.stdout)
    except ValueError:
        d = {}
    us = d.get("usage") or {}
    err = None
    if p.returncode != 0 or not d or d.get("is_error"):
        err = (p.stderr or d.get("result") or "claude failed")[:300]
    return {"input_tokens": us.get("input_tokens") or 0, "output_tokens": us.get("output_tokens") or 0,
            "cache_read": us.get("cache_read_input_tokens") or 0,
            "cache_write": us.get("cache_creation_input_tokens") or 0,
            "turns": d.get("num_turns"), "secs": secs, "cost_usd": d.get("total_cost_usd"),
            "answer": d.get("result") or "", "error": err}
