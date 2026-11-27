"""Claude Code headless (`claude -p`), read-only tools. Same setup as geolinux's 22 Nov dev_token_compare.sh.

API keys are always stripped, so it runs on your Claude login: $0 extra, but it uses your plan's usage limit.
cost_usd is what Claude Code reports the same work would cost at API price (for comparison only).

MCP: other MCP servers are off (--strict-mcp-config). An arm that ships a `.mcp.json` (e.g. CodeGraph) gets exactly
those servers, and their tools are allowed (read-only tools only: don't put write tools in an arm).
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
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY"):
        env.pop(k, None)
    mcp_file, mcp_tools = arm_mcp(Path(workdir))
    cmd = [exe, "-p", question, "--model", model["model"], "--output-format", "json",
           "--tools", "Read,Grep,Glob", "--allowedTools", ",".join(["Read", "Grep", "Glob"] + mcp_tools),
           "--disallowedTools", "Bash,Edit,Write,WebFetch,WebSearch",
           "--strict-mcp-config", "--permission-prompts", "none", "--no-session-persistence"]
    if mcp_file:
        cmd += ["--mcp-config", mcp_file]
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


def arm_mcp(workdir: Path) -> tuple[str | None, list[str]]:
    """The arm's own `.mcp.json` → (config file to load, its tools to allow). None when the arm has no MCP."""
    f = workdir / ".mcp.json"
    if not f.is_file():
        return None, []
    names = list((json.loads(f.read_text(encoding="utf-8")).get("mcpServers") or {}))
    return str(f), [f"mcp__{n}__*" for n in names]
