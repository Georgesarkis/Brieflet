"""Quality score per answer, 0-3, against reference points (questions/<repo>.refs.yaml).

The judge never sees which arm wrote the answer. It only says, per `must` point, whether the answer gets it right,
and lists wrong claims; the score is computed here, so it's the same rule for every arm:
  3 = every must point, nothing wrong · 2 = ≥ 2/3 of must points, no major error · 1 = some · 0 = none or a major error
Default judge = Claude Code on your login (free). judge.runner: anthropic = API (paid, gated like `run`).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

SYSTEM = """You grade an answer to a question about a code repository, against reference points from the real code.
For each MUST point: true if the answer states it correctly (wording may differ; it must be the same fact), else false.
List claims in the answer that contradict the reference or the code as the reference describes it ("wrong_claims"),
each with severity "major" (would send a developer the wrong way) or "minor". Do not reward length or style.
Answer ONLY with JSON: {"must": [true|false, ...], "wrong_claims": [{"claim": "...", "severity": "major|minor"}]}"""

CHARS_PER_TOKEN = 3.5


def prompt(question: str, refs: dict, answer: str) -> str:
    must = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(refs["must"]))
    nice = "\n".join(f"- {p}" for p in refs.get("nice", [])) or "(none)"
    return (f"QUESTION:\n{question}\n\nMUST POINTS:\n{must}\n\nNICE-TO-HAVE (do not grade, context only):\n{nice}\n\n"
            f"ANSWER TO GRADE:\n{answer[:12000]}")


def score(n_must: int, verdict: dict) -> int:
    hits = sum(1 for x in (verdict.get("must") or [])[:n_must] if x is True)
    major = any((w or {}).get("severity") == "major" for w in verdict.get("wrong_claims") or [])
    if major or hits == 0:
        return 0
    frac = hits / max(n_must, 1)
    if frac == 1 and not verdict.get("wrong_claims"):
        return 3
    return 2 if frac >= 2 / 3 else 1


def parse(text: str) -> dict | None:
    import re
    for cand in (text, (re.search(r"\{.*\}", text or "", re.S) or [None])[0]):
        try:
            d = json.loads(cand)
            if isinstance(d, dict) and isinstance(d.get("must"), list):
                return d
        except (TypeError, ValueError):
            pass
    return None


def ask(judge: dict, text: str) -> tuple[str, dict]:
    """→ (raw reply, usage dict with input/output tokens and cost_usd if known)."""
    if judge.get("runner", "claude_code") == "claude_code":
        exe = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
        env = dict(os.environ)
        for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY"):
            env.pop(k, None)
        p = subprocess.run([exe, "-p", SYSTEM + "\n\n" + text, "--model", judge.get("model", "opus"), "--output-format", "json",
                            "--tools", "", "--strict-mcp-config", "--no-session-persistence"],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600, cwd="/tmp")
        try:
            d = json.loads(p.stdout)
        except ValueError:
            return "", {}
        u = d.get("usage") or {}
        return d.get("result") or "", {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
                                       "cost_usd": d.get("total_cost_usd")}
    import anthropic
    resp = anthropic.Anthropic().messages.create(model=judge["model"], max_tokens=4000, system=SYSTEM,
                                                 messages=[{"role": "user", "content": text}])
    out = "".join(b.text for b in resp.content if b.type == "text")
    return out, {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}


def refs_for(qfile: Path) -> dict:
    f = qfile.with_name(qfile.stem + ".refs.yaml")
    return yaml.safe_load(open(f)) if f.exists() else {}
