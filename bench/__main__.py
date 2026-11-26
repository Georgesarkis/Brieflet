"""Brieflet benchmark: does a short AI context make a model read fewer tokens and answer faster, without worse answers?

  python -m bench plan   [-c bench.yaml]                      matrix + cost estimate. Never spends.
  python -m bench run    [-c bench.yaml] --yes [--only MODEL]  runs it. Paid runners need --yes AND estimate ≤ max_usd.
  python -m bench report [-c bench.yaml]                      median table per repo × model × arm.

Money rule: nothing that costs money runs without `--yes`, and `run` re-checks the estimate against max_usd first.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import statistics as st
import sys
import tempfile
from pathlib import Path

import yaml

from . import runners

HERE = Path(__file__).resolve().parent
FREE_RUNNERS = {"fake"}


def load(path: str) -> dict:
    cfg = yaml.safe_load(open(path))
    cfg["_dir"] = Path(path).resolve().parent
    cfg["_prices"] = yaml.safe_load(open(HERE / "prices.yaml"))
    return cfg


def expand(cfg: dict, s: str, repo: str = "") -> Path:
    s = s.replace("{artifacts}", str(cfg.get("artifacts", ""))).replace("{repo}", repo)
    p = Path(os.path.expanduser(s))
    return p if p.is_absolute() else cfg["_dir"] / p


def questions(cfg: dict, repo: str) -> list[dict]:
    return yaml.safe_load(open(expand(cfg, cfg["repos"][repo]["questions"])))["questions"]


def price_of(cfg: dict, m: dict) -> dict | None:
    table = cfg["_prices"].get("openai" if m["runner"] == "openai" else "anthropic", {}) or {}
    key = {"sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5", "haiku": "claude-haiku-5-5"}.get(m["model"], m["model"])
    return table.get(key)


def paid(m: dict) -> bool:
    if m["runner"] in FREE_RUNNERS:
        return False
    return not (m["runner"] == "claude_code" and m.get("billing", "subscription") == "subscription")


def results_file(cfg: dict) -> Path:
    d = expand(cfg, cfg.get("results", "results"))
    d.mkdir(parents=True, exist_ok=True)
    return d / "runs.jsonl"


def rows(cfg: dict) -> list[dict]:
    f = results_file(cfg)
    return [json.loads(l) for l in open(f) if l.strip()] if f.exists() else []


def per_run_tokens(cfg: dict, arm: str, model: str) -> tuple[dict, str]:
    """Measured median from earlier runs of this arm + model if there are ≥3, else the prior from the config."""
    done = [r for r in rows(cfg) if r["arm"] == arm and r["model"] == model and not r.get("error")]
    if len(done) >= 3:
        inp = st.median(r["input_tokens"] + r["cache_read"] + r["cache_write"] for r in done)
        out = st.median(r["output_tokens"] for r in done)
        return {"input": inp, "output": out}, f"measured ({len(done)} runs)"
    pri = cfg.get("prior_tokens", {})
    return pri.get(arm) or pri.get("default") or {"input": 80000, "output": 2000}, "prior"


def estimate_run(tokens: dict, price: dict | None) -> tuple[float, float] | None:
    """(low, high) USD for one question run. Low = most input read from cache (tool loops re-send the prefix),
    high = no cache hits at all. The budget check uses high."""
    if not price:
        return None
    i, o = tokens["input"], tokens["output"]
    out = o * price["output"]
    low = (0.15 * i * price["input"] + 0.15 * i * price.get("cache_write", price["input"])
           + 0.70 * i * price.get("cache_read", price["input"]) + out) / 1e6
    high = (i * price["input"] + out) / 1e6
    return low, high


def matrix(cfg: dict, only: str | None):
    for repo in cfg["repos"]:
        for m in cfg["models"]:
            if only and m["name"] != only:
                continue
            for arm in cfg["arms"]:
                yield repo, m, arm, questions(cfg, repo)


def plan(cfg: dict, only: str | None = None, quiet: bool = False) -> dict:
    reps = cfg.get("repeats", 3)
    tot = {"runs": 0, "paid_runs": 0, "low": 0.0, "high": 0.0, "unpriced": set(), "sub_runs": 0, "sub_usd": 0.0}
    lines = [f"{'repo':10} {'model':12} {'arm':14} {'runs':>5} {'tokens/run':>11} {'basis':18} {'est. USD':>15}"]
    for repo, m, arm, qs in matrix(cfg, only):
        n = len(qs) * reps
        tok, basis = per_run_tokens(cfg, arm, m["name"])
        est = estimate_run(tok, price_of(cfg, m))
        tot["runs"] += n
        if not paid(m):
            usd = "$0 (subscription)" if m["runner"] == "claude_code" else "$0"
            tot["sub_runs"] += n if m["runner"] == "claude_code" else 0
            if est and m["runner"] == "claude_code":
                tot["sub_usd"] += n * est[1]
        elif est is None:
            usd = "NO PRICE"
            tot["unpriced"].add(m["name"])
            tot["paid_runs"] += n
        else:
            usd = f"${n * est[0]:.2f}–{n * est[1]:.2f}"
            tot["paid_runs"] += n
            tot["low"] += n * est[0]
            tot["high"] += n * est[1]
        lines.append(f"{repo:10} {m['name']:12} {arm:14} {n:5} {int(tok['input']):>11,} {basis:18} {usd:>15}")
    if not quiet:
        print("\n".join(lines))
        print(f"\nTotal: {tot['runs']} runs. Paid: {tot['paid_runs']} runs, estimate ${tot['low']:.2f}–${tot['high']:.2f} "
              f"(budget max_usd ${cfg.get('max_usd', 0)}).")
        if tot["sub_runs"]:
            print(f"Subscription runs: {tot['sub_runs']} (no extra money; ≈ ${tot['sub_usd']:.2f} of API-price usage "
                  f"against your plan's limit, may hit rate limits).")
        if tot["unpriced"]:
            print(f"No price for: {', '.join(sorted(tot['unpriced']))} → fill bench/prices.yaml or they can't run.")
    return tot


def prepare(cfg: dict, repo: str, arm: str, tmp: Path) -> Path:
    rc = cfg["repos"][repo]
    src = expand(cfg, rc["path"])
    dst = tmp / f"{repo}-{arm}"
    if dst.exists():
        return dst
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git"), symlinks=False)
    for s in rc.get("strip", []):
        p = dst / s
        shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
    a = cfg["arms"][arm] or {}
    for ov in a.get("overlay", []):
        ov = expand(cfg, ov, repo)
        if not ov.is_dir():
            raise SystemExit(f"arm {arm}: overlay folder missing: {ov} (generate it first)")
        shutil.copytree(ov, dst, dirs_exist_ok=True)
    if a.get("claude_md"):
        (dst / "CLAUDE.md").write_text(a["claude_md"])
    return dst


def run(cfg: dict, yes: bool, only: str | None) -> int:
    tot = plan(cfg, only)
    max_usd = float(cfg.get("max_usd", 0))
    if tot["paid_runs"]:
        if tot["unpriced"]:
            print("\nRefused: some paid models have no price."); return 2
        if not yes:
            print("\nRefused: paid runs need --yes (after you've read the estimate above)."); return 2
        if tot["high"] > max_usd:
            print(f"\nRefused: high estimate ${tot['high']:.2f} > max_usd ${max_usd}. Lower repeats/questions or raise max_usd."); return 2
    reps, per_run_cap = cfg.get("repeats", 3), float(cfg.get("max_usd_per_run", 1.0))
    out = results_file(cfg)
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="brieflet-bench-") as t:
        tmp = Path(t)
        for repo in cfg["repos"]:
            for m in cfg["models"]:
                if only and m["name"] != only:
                    continue
                fn, price = runners.get(m["runner"]), price_of(cfg, m)
                for q in questions(cfg, repo):
                    for r in range(1, reps + 1):
                        for arm in cfg["arms"]:  # arms interleaved: time-of-day / cache effects hit all arms alike
                            if paid(m):
                                tok, _ = per_run_tokens(cfg, arm, m["name"])
                                nxt = estimate_run(tok, price)[1]
                                if spent + min(nxt, per_run_cap) > max_usd:
                                    print(f"STOP: spent ${spent:.2f}, next run could pass max_usd ${max_usd}."); return 3
                            wd = prepare(cfg, repo, arm, tmp)
                            row = fn(q["text"], wd, m, price, per_run_cap)
                            if paid(m):
                                spent += row.get("cost_usd") or 0
                            row.update(run=run_id, t=dt.datetime.now().isoformat(timespec="seconds"), repo=repo,
                                       sha=cfg["repos"][repo].get("sha"), model=m["name"], runner=m["runner"],
                                       model_id=m["model"], arm=arm, q=q["id"], qtype=q.get("type"), rep=r,
                                       question=q["text"])
                            with open(out, "a") as fh:
                                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                            tin = row["input_tokens"] + row["cache_read"] + row["cache_write"]
                            print(f"{repo} {m['name']} {q['id']} #{r} {arm:14} in={tin:>8,} out={row['output_tokens']:>6,} "
                                  f"{row['secs']:>6}s" + (f"  ERROR {row['error']}" if row.get("error") else ""))
    print(f"\nDone. Paid spend this run ≈ ${spent:.2f}. Rows → {out}")
    return 0


def report(cfg: dict) -> int:
    rs = [r for r in rows(cfg) if not r.get("error")]
    if not rs:
        print("no results yet"); return 0
    med = lambda xs: st.median(xs) if xs else 0
    L = ["| repo | model | arm | input tokens (sum of q medians) | vs none | seconds | USD (API price) | ok/all |",
         "|---|---|---|---|---|---|---|---|"]
    allrows = rows(cfg)
    for repo in sorted({r["repo"] for r in rs}):
        for model in sorted({r["model"] for r in rs if r["repo"] == repo}):
            base = None
            for arm in cfg["arms"]:
                g = [r for r in rs if r["repo"] == repo and r["model"] == model and r["arm"] == arm]
                if not g:
                    continue
                qs = sorted({r["q"] for r in g})
                tin = sum(med([r["input_tokens"] + r["cache_read"] + r["cache_write"] for r in g if r["q"] == q]) for q in qs)
                secs = sum(med([r["secs"] for r in g if r["q"] == q]) for q in qs)
                usd = sum(med([r.get("cost_usd") or 0 for r in g if r["q"] == q]) for q in qs)
                if arm == "none":
                    base = tin
                vs = f"{(tin / base - 1) * 100:+.0f}%" if base and arm != "none" else ""
                n_all = sum(1 for r in allrows if r["repo"] == repo and r["model"] == model and r["arm"] == arm)
                L.append(f"| {repo} | {model} | {arm} | {tin:,.0f} | {vs} | {secs:.0f} | {usd:.3f} | {len(g)}/{n_all} |")
    print("\n".join(L))
    print("\nTokens only. Quality (judge scores) comes next: fewer tokens with a worse answer is not a win.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bench")
    ap.add_argument("cmd", choices=["plan", "run", "report"])
    ap.add_argument("-c", "--config", default="bench.yaml")
    ap.add_argument("--yes", action="store_true", help="allow paid runs (after reading `plan`)")
    ap.add_argument("--only", help="only this model name from the config")
    a = ap.parse_args(argv)
    cfg = load(a.config)
    if a.cmd == "plan":
        plan(cfg, a.only); return 0
    if a.cmd == "run":
        return run(cfg, a.yes, a.only)
    return report(cfg)


if __name__ == "__main__":
    sys.exit(main())
