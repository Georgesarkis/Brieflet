"""View: the plan table + totals that `bench plan` and `bench run` print."""
from __future__ import annotations

from ..application.plan_benchmark import BenchPlan, PlanLine
from ..domain.pricing import is_paid


def _usd(l: PlanLine) -> str:
    if not is_paid(l.model):
        return "$0 (subscription)" if l.model["runner"] == "claude_code" else "$0"
    if l.estimate is None:
        return "NO PRICE"
    return f"${l.runs * l.estimate[0]:.2f}–{l.runs * l.estimate[1]:.2f}"


def render(plan: BenchPlan) -> str:
    t = plan.totals
    out = [f"{'repo':10} {'model':12} {'arm':14} {'runs':>5} {'tokens/run':>11} {'basis':18} {'est. USD':>15}"]
    out += [f"{l.repo:10} {l.model['name']:12} {l.arm:14} {l.runs:5} {int(l.tokens['input']):>11,} {l.basis:18} {_usd(l):>15}"
            for l in plan.lines]
    out.append(f"\nTotal: {t.runs} runs. Paid: {t.paid_runs} runs, estimate ${t.low:.2f}–${t.high:.2f} "
               f"(budget max_usd ${plan.max_usd:g}).")
    if t.sub_runs:
        out.append(f"Subscription runs: {t.sub_runs} (no extra money; ≈ ${t.sub_usd:.2f} of API-price usage "
                   f"against your plan's limit, may hit rate limits).")
    if t.unpriced:
        out.append(f"No price for: {', '.join(sorted(t.unpriced))} → fill bench/prices.yaml or they can't run.")
    return "\n".join(out)
