"""Use case: the benchmark matrix + a cost estimate. Never spends anything."""
from __future__ import annotations

import statistics as st
from dataclasses import dataclass, field

from ..domain.pricing import estimate_run, is_paid, is_subscription
from ..domain.results import input_tokens
from .config import BenchConfig
from .ports import ResultsStore

MIN_MEASURED = 3   # with this many earlier runs, use their median instead of the config's prior


@dataclass
class PlanLine:
    repo: str
    model: dict
    arm: str
    runs: int
    tokens: dict
    basis: str
    estimate: tuple[float, float] | None


@dataclass
class PlanTotals:
    runs: int = 0
    paid_runs: int = 0
    low: float = 0.0
    high: float = 0.0
    unpriced: set = field(default_factory=set)
    sub_runs: int = 0
    sub_usd: float = 0.0          # API-price value of subscription runs (counts against the plan's limit)
    learn_runs: int = 0           # the learning pass part of `runs` (run by `bench learn`, not `bench run`)


@dataclass
class BenchPlan:
    lines: list[PlanLine]
    totals: PlanTotals
    max_usd: float


def tokens_per_run(cfg: BenchConfig, store: ResultsStore, arm: str, model: str) -> tuple[dict, str]:
    """Measured median from earlier runs of this arm + model if there are enough, else the prior from the config."""
    done = [r for r in store.runs() if r["arm"] == arm and r["model"] == model and not r.get("error")]
    if len(done) >= MIN_MEASURED:
        return ({"input": st.median(input_tokens(r) for r in done), "output": st.median(r["output_tokens"] for r in done)},
                f"measured ({len(done)} runs)")
    return cfg.prior_tokens(arm), "prior"


class PlanBenchmark:
    def __init__(self, cfg: BenchConfig, store: ResultsStore):
        self.cfg, self.store = cfg, store

    def execute(self, only: str | None = None) -> BenchPlan:
        lines, tot = [], PlanTotals()
        for repo, m, arm, qs in self.cfg.matrix(only):
            learn_n = len(qs) if self.cfg.is_learn(arm) else 0
            n = len(qs) * self.cfg.repeats + learn_n
            tok, basis = tokens_per_run(self.cfg, self.store, arm, m["name"])
            est = estimate_run(tok, self.cfg.price(m))
            self._add(tot, m, n, est)
            tot.learn_runs += learn_n
            lines.append(PlanLine(repo, m, arm, n, tok, basis, est))
        return BenchPlan(lines, tot, self.cfg.max_usd)

    @staticmethod
    def _add(tot: PlanTotals, m: dict, n: int, est: tuple[float, float] | None) -> None:
        tot.runs += n
        if not is_paid(m):
            if is_subscription(m):
                tot.sub_runs += n
                tot.sub_usd += n * est[1] if est else 0
            return
        tot.paid_runs += n
        if est is None:
            tot.unpriced.add(m["name"])
            return
        tot.low += n * est[0]
        tot.high += n * est[1]
