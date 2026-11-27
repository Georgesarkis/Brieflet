"""Dashboard: one self-contained HTML page per config (results, models, generated docs), plus `index.html` next to
the results folders: one button per tested repo (pick one or several) with each repo's results. `python -m bench dashboard -c <cfg>`.

No server, no build. Rebuilt after every run / learn / judge row; the page reloads itself when it changes.
Mermaid is the only external script (component diagram); offline, the diagram source is shown instead.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

from ...application.config import BenchConfig
from ...domain.results import arm_stats, common_questions
from . import results_html as R
from . import setup_html as S
from . import hub as H
from .page import MARK, PAGE
from .repo_info import info as repo_info
from .markdown_html import esc

DOCS_ARM = "brieflet"


def _meta(cfg: BenchConfig, repo: str) -> dict:
    f = cfg.artifacts_dir(repo) / "meta.yaml"
    return (yaml.safe_load(open(f)) or {}) if f.exists() else {}


def _results(cfg: BenchConfig, repo: str, rows: list[dict], verdicts: dict):
    """(model, stats, question ids, question texts, last run time) for one repo of one config."""
    ok = [r for r in rows if not r.get("error") and r["repo"] == repo]
    model = (sorted({r["model"] for r in ok}) or [m["name"] for m in cfg.models])[0]
    mine = [r for r in ok if r["model"] == model]
    stats = arm_stats(mine, verdicts, cfg.arms)
    qs = sorted(common_questions(mine, cfg.arms), key=lambda q: int(re.sub(r"\D", "", q) or 0))
    qtext = {q["id"]: q["text"] for q in cfg.questions[repo]}
    return model, stats, qs, qtext, max((r["t"] for r in ok), default="")


def build(cfg: BenchConfig, rows: list[dict], verdicts: dict, status: str = "", learned_dir=None) -> str:
    repo = next(iter(cfg.repos))
    meta = _meta(cfg, repo)
    model, stats, qs, qtext, when = _results(cfg, repo, rows, verdicts)
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


def publish(cfg: BenchConfig, store, status: str = "", quiet: bool = False, log=print, siblings=None) -> None:
    """Write dashboard.html next to runs.jsonl, atomically, then the all-repos index.html (siblings() gives every
    (config, store) sharing this results root). Never lets the page break a finished run."""
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
    try:
        idx = publish_index(cfg.results_dir.parent, siblings()) if siblings else None
        if idx and not quiet:
            log(f"all repos: {idx}")
    except Exception as e:  # noqa: BLE001
        log(f"repo overview not rebuilt: {e}")


# ------------------------------------------------------------------------------------------- all repos (index.html)
def build_index(entries: list, root: Path) -> str:
    """entries: (config, store) for every bench config sharing this results root."""
    repos = []
    for c, store in entries:
        rows, verdicts = store.runs(), store.verdicts()
        for repo, rc in c.repos.items():
            if not any(r["repo"] == repo for r in rows):
                continue
            model, stats, qs, qtext, when = _results(c, repo, rows, verdicts)
            path = rc.get("path")
            ri = repo_info(repo, rc, _meta(c, repo), c.path(path) if path else None)
            page = store.runs_path.with_name("dashboard.html").relative_to(root).as_posix()
            body = R.hero(stats, model, len(qs)) + R.bars(stats) + R.table(stats) + R.per_question(stats, qs, qtext)
            nums = {a: {"tokens": st.tokens, "usd": st.usd, "secs": st.secs, "quality": st.quality, "good": st.good,
                        "scored": st.n_scored} for a, st in stats.items()}
            repos.append(H.Repo(ri, body, page, model, sum(s.runs for s in stats.values()), when, nums))
    return H.page(repos, dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def publish_index(root: Path, entries: list) -> Path | None:
    """Write <results root>/index.html: one button per tested repo. Skipped when no config has runs yet."""
    entries = [(c, st) for c, st in entries if st.runs_path.exists()]
    if not entries:
        return None
    out = Path(root) / "index.html"
    tmp = out.with_suffix(".tmp")
    tmp.write_text(build_index(entries, Path(root)), encoding="utf-8")
    tmp.replace(out)
    return out
