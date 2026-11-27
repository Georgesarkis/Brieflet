"""Result rows (one per answered question) and the per-setup statistics the report and dashboard show.

Row: answer, input_tokens, cache_read, cache_write, output_tokens, turns, secs, cost_usd, error
     + run, t, repo, sha, model, runner, model_id, arm, q, qtype, rep, question
"""
from __future__ import annotations

import statistics as st
from dataclasses import dataclass, field

from .scoring import GOOD


def row_key(r: dict) -> str:
    return f'{r["run"]}|{r["repo"]}|{r["model"]}|{r["arm"]}|{r["q"]}|{r["rep"]}'


def input_tokens(r: dict) -> int:
    """All input the model read: new + cache read + cache write."""
    return r["input_tokens"] + r["cache_read"] + r["cache_write"]


def _median(xs):
    return st.median(xs) if xs else None


@dataclass
class ArmStats:
    tokens: float                 # sum over questions of the median input tokens per question
    secs: float
    usd: float
    runs: int
    per_q: dict = field(default_factory=dict)      # question → median input tokens
    q_score: dict = field(default_factory=dict)    # question → median quality
    quality: float | None = None
    n_scored: int = 0
    good: int = 0
    per_good: float | None = None                  # input tokens per good answer


def common_questions(rows: list[dict], arms: list[str]) -> set[str]:
    """Questions every setup (that has rows) answered: sums are only comparable over these."""
    have = [h for h in ({r["q"] for r in rows if r["arm"] == a} for a in arms) if h]
    return set.intersection(*have) if have else set()


def arm_stats(rows: list[dict], verdicts: dict, arms: list[str]) -> dict[str, ArmStats]:
    """rows = successful rows of ONE repo + model."""
    qs = common_questions(rows, arms)
    out = {}
    for arm in arms:
        g = [r for r in rows if r["arm"] == arm]
        if g:
            out[arm] = _one_arm(g, verdicts, qs)
    return out


def _score(verdicts: dict, r: dict):
    v = verdicts.get(row_key(r))
    return v.get("score") if v else None


def _one_arm(g: list[dict], verdicts: dict, qs: set[str]) -> ArmStats:
    per_q = {q: _median([input_tokens(r) for r in g if r["q"] == q]) for q in qs}
    sc = [s for r in g if (s := _score(verdicts, r)) is not None]
    good = sum(1 for s in sc if s >= GOOD)
    judged_tokens = sum(input_tokens(r) for r in g if row_key(r) in verdicts)
    return ArmStats(
        tokens=sum(v for v in per_q.values() if v is not None),
        secs=sum(_median([r["secs"] for r in g if r["q"] == q]) or 0 for q in qs),
        usd=sum(_median([r.get("cost_usd") or 0 for r in g if r["q"] == q]) or 0 for q in qs),
        runs=len(g), per_q=per_q,
        q_score={q: _median([s for r in g if r["q"] == q and (s := _score(verdicts, r)) is not None]) for q in qs},
        quality=st.mean(sc) if sc else None, n_scored=len(sc), good=good,
        per_good=judged_tokens / good if good else None)
