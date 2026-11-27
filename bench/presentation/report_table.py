"""View: `bench report`, a Markdown table per repo × model × arm."""
from __future__ import annotations

from ..domain.results import ArmStats, arm_stats, common_questions

HEADER = ["| repo | model | arm | input tokens (sum of q medians) | vs none | seconds | USD (API price) | ok/all "
          "| quality 0-3 (mean) | good answers (≥2) | input tokens per good answer |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]


def _row(repo: str, model: str, arm: str, s: ArmStats, base: float | None, n_all: int) -> str:
    vs = f"{(s.tokens / base - 1) * 100:+.0f}%" if base and arm != "none" else ""
    qual = f"{s.quality:.2f} (n={s.n_scored})" if s.quality is not None else "–"
    per_good = f"{s.per_good:,.0f}" if s.per_good else "–"
    return (f"| {repo} | {model} | {arm} | {s.tokens:,.0f} | {vs} | {s.secs:.0f} | {s.usd:.3f} | {s.runs}/{n_all} "
            f"| {qual} | {s.good}/{s.n_scored} | {per_good} |")


def render(all_rows: list[dict], verdicts: dict, arms: list[str]) -> list[str]:
    """→ lines to print: one 'summed over' note per repo/model, then the table."""
    ok = [r for r in all_rows if not r.get("error")]
    if not ok:
        return ["no results yet"]
    notes, table = [], list(HEADER)
    for repo in sorted({r["repo"] for r in ok}):
        for model in sorted({r["model"] for r in ok if r["repo"] == repo}):
            g = [r for r in ok if r["repo"] == repo and r["model"] == model]
            common = sorted(common_questions(g, arms))
            notes.append(f"{repo} / {model}: tokens, seconds and USD are summed over the {len(common)} questions every "
                         f"setup answered: {', '.join(common)}")
            stats = arm_stats(g, verdicts, arms)
            base = stats["none"].tokens if "none" in stats else None
            for arm, s in stats.items():
                n_all = sum(1 for r in all_rows if r["repo"] == repo and r["model"] == model and r["arm"] == arm)
                table.append(_row(repo, model, arm, s, base, n_all))
    out = notes + ["\n".join(table)]
    if not verdicts:
        out.append("\nNo quality scores yet: run `judge`. Fewer tokens with a worse answer is not a win.")
    return out
