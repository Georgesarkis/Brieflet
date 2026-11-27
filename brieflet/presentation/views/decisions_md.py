"""Views: one decision record (docs/decisions/NNNN-*.md) and the DECISIONS.md index."""
from __future__ import annotations

from datetime import date

from ...domain.decisions import STATUS_INFERRED, DecisionRecord

INDEX = "DECISIONS.md"


def render_record(r: DecisionRecord, today: date | None = None) -> str:
    c = r.candidate
    ev = [f"- `{x.split(' ', 1)[0][:7]}` {x.split(' ', 1)[1] if ' ' in x else ''}".rstrip() for x in c.commits]
    ev += [f"- `{p}`" for p in c.evidence[:12]]
    return "\n".join([
        f"# {r.number}. {r.title}", "", f"- **Status:** {STATUS_INFERRED}",
        f"- **Date:** {(today or date.today()).isoformat()}", f"- **Type:** {r.type}", f"- **Confidence:** {r.confidence}", "",
        "## Context", "", r.context, "", "## Decision", "", r.decision, "",
        "## Consequences", "", r.consequences, "", "## Evidence", "",
        "Inferred by a model from these commits and files:", "", *ev, "",
        f"<!-- brieflet key: {c.key} -->", ""])


def render_index(records: list[DecisionRecord]) -> str:
    rows = [f"| [{r.number}]({r.path}) | {r.title} | {STATUS_INFERRED} |" for r in records]
    return "\n".join(["# Architecture decisions", "",
                      "One row per decision record in `docs/decisions/`. Status *Inferred* = written by a model "
                      "from the code and commits; a human changes it to *Accepted* (or fixes it).", "",
                      "| # | Decision | Status |", "|---|---|---|", *rows, ""])
