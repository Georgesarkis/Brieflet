"""Dashboard: one self-contained HTML page (results, models, generated docs). `python -m bench dashboard -c <cfg>`.

No server, no build. Rebuilt after every run / learn / judge row; the page reloads itself when it changes.
Mermaid is the only external script (component diagram); offline, the diagram source is shown instead.
"""
from __future__ import annotations

import datetime as dt
import re

import yaml

from ...application.config import BenchConfig
from ...domain.results import arm_stats, common_questions
from . import results_html as R
from . import setup_html as S
from .page import MARK, PAGE
from .markdown_html import esc

DOCS_ARM = "brieflet"


def build(cfg: BenchConfig, rows: list[dict], verdicts: dict, status: str = "", learned_dir=None) -> str:
    repo = next(iter(cfg.repos))
    art = cfg.artifacts_dir(repo)
    meta = (yaml.safe_load(open(art / "meta.yaml")) or {}) if (art / "meta.yaml").exists() else {}
    ok = [r for r in rows if not r.get("error") and r["repo"] == repo]
    model = (sorted({r["model"] for r in ok}) or [m["name"] for m in cfg.models])[0]
    mine = [r for r in ok if r["model"] == model]
    stats = arm_stats(mine, verdicts, cfg.arms)
    qs = sorted(common_questions(mine, cfg.arms), key=lambda q: int(re.sub(r"\D", "", q) or 0))
    qtext = {q["id"]: q["text"] for q in cfg.questions[repo]}
    when = max((r["t"] for r in ok), default="")
    return PAGE.format(
        title=f"Brieflet benchmark · {esc(meta.get('repo', repo))}",
        mark=MARK, repo=esc(meta.get("repo", repo)), sha=esc(str(cfg.repos[repo].get("sha") or "")[:7]),
        when=esc(when.replace("T", " ")), runs=sum(s.runs for s in stats.values()), model=esc(model),
        hero=R.hero(stats, model, len(qs)), bars=R.bars(stats), table=R.table(stats),
        perq=R.per_question(stats, qs, qtext), models=S.models(meta, cfg.models, cfg.data.get("judge") or {}),
        docs=_docs(cfg, repo, learned_dir) or "<p class='muted'>No generated docs found.</p>",
        built=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        live=(f"<div class='live' role='status'><span class='dot'></span>{esc(status)}</div>" if status else ""))


def _docs(cfg: BenchConfig, repo: str, learned_dir) -> str:
    art = cfg.artifacts_dir(repo)
    out = "".join(S.doc_files(d) for ov in cfg.arm(DOCS_ARM).get("overlay", []) if (d := cfg.path(ov, repo)).is_dir()) \
        if DOCS_ARM in cfg.arms else ""
    out += S.graph_compare(art / "graphify-ast/docs/architecture/GRAPH_REPORT.md", art / "brieflet/AI_CONTEXT.md")
    return out + S.learned_folds(learned_dir)


def publish(cfg: BenchConfig, store, status: str = "", quiet: bool = False, log=print) -> None:
    """Write dashboard.html next to runs.jsonl, atomically. Never lets the page break a finished run."""
    out = store.runs_path.with_name("dashboard.html")
    try:
        html = build(cfg, store.runs(), store.verdicts(), status, store.learned_dir)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(html, encoding="utf-8")
        tmp.replace(out)  # atomic: the page never sees a half-written file
        if not quiet:
            log(f"dashboard: {out}")
    except Exception as e:  # noqa: BLE001 - the dashboard is a side view; a broken page must not stop the benchmark
        log(f"dashboard not rebuilt: {e}")
