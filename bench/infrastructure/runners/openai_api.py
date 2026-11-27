"""OpenAI models via Chat Completions function calling, same three tools and system prompt as the Claude runner."""
from __future__ import annotations

import json
import time
from pathlib import Path

import openai

from ...domain.pricing import usage_cost
from .repo_tools import SPECS, RepoTools
from .harness import SYSTEM, empty_usage, project_instructions


def run(question: str, workdir: Path, model: dict, price: dict | None, max_usd_this_run: float) -> dict:
    client = openai.OpenAI()  # OPENAI_API_KEY
    tools = RepoTools(workdir)
    defs = [{"type": "function", "function": {"name": s["name"], "description": s["description"],
                                              "parameters": s["schema"], "strict": True}} for s in SPECS]
    messages = [{"role": "system", "content": SYSTEM + project_instructions(workdir)},
                {"role": "user", "content": question}]
    u = empty_usage()
    turns, t0, answer, error = 0, time.time(), "", None

    while True:
        turns += 1
        try:
            resp = client.chat.completions.create(model=model["model"], messages=messages, tools=defs)
        except openai.APIStatusError as e:
            error = f"api {e.status_code}: {e.message}"[:300]
            break
        except openai.APIConnectionError as e:
            error = f"connection: {e}"[:300]
            break
        us = resp.usage
        cached = getattr(getattr(us, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        u["input_tokens"] += (us.prompt_tokens or 0) - cached
        u["cache_read"] += cached
        u["output_tokens"] += us.completion_tokens or 0
        spent = usage_cost(u, price) or 0

        msg = resp.choices[0].message
        if not msg.tool_calls:
            answer = msg.content or ""
            if resp.choices[0].finish_reason == "length":
                error = "max_tokens"
            break
        messages.append(msg.model_dump(exclude_none=True))
        if turns >= model.get("max_turns", 40):
            error = "max_turns"
            break
        if spent >= max_usd_this_run:
            error = f"run budget ${max_usd_this_run:.2f} reached"
            break
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                text, _ = tools.call(tc.function.name, args)
            except json.JSONDecodeError:
                text = "error: arguments were not valid JSON"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})

    return {**u, "turns": turns, "secs": round(time.time() - t0, 1), "cost_usd": usage_cost(u, price),
            "answer": answer, "error": error}
