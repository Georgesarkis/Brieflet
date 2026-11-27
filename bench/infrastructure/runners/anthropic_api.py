"""Claude via the Messages API, own tool loop (so every turn's usage is counted and the budget can stop it).

No server-side fallbacks on purpose: a refusal that silently switched models would mix two models in one cell.
A refusal is recorded as an error row instead.
"""
from __future__ import annotations

import time
from pathlib import Path

import anthropic

from ...domain.pricing import usage_cost
from .repo_tools import SPECS, RepoTools
from .harness import SYSTEM, empty_usage, project_instructions


def run(question: str, workdir: Path, model: dict, price: dict | None, max_usd_this_run: float) -> dict:
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY or `ant auth login` profile
    tools = RepoTools(workdir)
    defs = [{"name": s["name"], "description": s["description"], "input_schema": s["schema"], "strict": True}
            for s in SPECS]
    system = SYSTEM + project_instructions(workdir)
    messages = [{"role": "user", "content": question}]
    u = empty_usage()
    turns, t0, answer, error = 0, time.time(), "", None
    params = dict(model=model["model"], max_tokens=model.get("max_tokens", 16000), system=system, tools=defs,
                  cache_control={"type": "ephemeral"})
    if model.get("effort"):
        params["output_config"] = {"effort": model["effort"]}

    while True:
        turns += 1
        try:
            resp = client.messages.create(messages=messages, **params)
        except anthropic.APIStatusError as e:
            error = f"api {e.status_code}: {e.message}"[:300]
            break
        except anthropic.APIConnectionError as e:
            error = f"connection: {e}"[:300]
            break
        us = resp.usage
        u["input_tokens"] += us.input_tokens or 0
        u["output_tokens"] += us.output_tokens or 0
        u["cache_read"] += getattr(us, "cache_read_input_tokens", 0) or 0
        u["cache_write"] += getattr(us, "cache_creation_input_tokens", 0) or 0
        spent = usage_cost(u, price) or 0

        if resp.stop_reason == "refusal":
            error = "refusal"
            break
        if resp.stop_reason == "end_turn" or resp.stop_reason == "max_tokens":
            answer = "\n".join(b.text for b in resp.content if b.type == "text")
            if resp.stop_reason == "max_tokens":
                error = "max_tokens"
            break
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "pause_turn":
            continue
        if turns >= model.get("max_turns", 40):
            error = "max_turns"
            break
        if spent >= max_usd_this_run:
            error = f"run budget ${max_usd_this_run:.2f} reached"
            break
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                text, is_err = tools.call(b.name, dict(b.input))
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": is_err})
        messages.append({"role": "user", "content": results})

    return {**u, "turns": turns, "secs": round(time.time() - t0, 1), "cost_usd": usage_cost(u, price),
            "answer": answer, "error": error}
