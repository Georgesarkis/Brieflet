"""Brieflet benchmark: does a short AI context make a model read fewer tokens and answer faster, without worse answers?

  python -m bench plan   [-c bench.yaml]                      matrix + cost estimate. Never spends.
  python -m bench learn  [-c bench.yaml] [--yes] [--only MODEL]  learning pass for arms with `learn:` (writes LEARNED.md per fold).
  python -m bench run    [-c bench.yaml] --yes [--only MODEL] [--resume]  runs it. Paid runners need --yes AND estimate ≤ max_usd.
  python -m bench judge  [-c bench.yaml] [--yes]               quality 0-3 per answer (free via Claude Code by default).
  python -m bench dashboard [-c bench.yaml]                   one HTML page: results, models, generated docs.
  python -m bench report [-c bench.yaml]                      median table per repo × model × arm.

Money rule: nothing that costs money runs without `--yes`, and `run` re-checks the estimate against max_usd first.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import statistics as st
import sys
import tempfile
from pathlib import Path

import yaml

from brieflet import learned as L

from . import judge as J
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
        n = len(qs) * reps + (len(qs) if is_learn(cfg, arm) else 0)  # + one learning pass
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


def is_learn(cfg: dict, arm: str) -> bool:
    return bool((cfg["arms"][arm] or {}).get("learn"))


def folds(cfg: dict, repo: str) -> list[list[str]]:
    """Question ids split in N folds (default 2: first half / second half). Learn on one, measure on the others."""
    ids = [q["id"] for q in questions(cfg, repo)]
    n = int((cfg.get("learn") or {}).get("folds", 2))
    k = -(-len(ids) // n)
    return [ids[i:i + k] for i in range(0, len(ids), k)]


def fold_of(cfg: dict, repo: str, qid: str) -> int:
    return next(i for i, f in enumerate(folds(cfg, repo)) if qid in f)


def learned_file(cfg: dict, repo: str, model: str, arm: str, fold: int) -> Path:
    return results_file(cfg).parent / "learned" / repo / model / arm / f"fold{fold + 1}.md"


def add_rule(wd: Path) -> None:
    cm = wd / "CLAUDE.md"
    txt = cm.read_text(encoding="utf-8") if cm.exists() else ""
    if "LEARNED.md" not in txt or "When the docs were not enough" not in txt:
        cm.write_text(txt.rstrip() + "\n" + L.RULE, encoding="utf-8")


def prepare_learn(cfg: dict, repo: str, model: str, arm: str, qid: str, tmp: Path) -> Path:
    """Measured run of a learn arm: base arm + LEARNED.md made from the OTHER folds only (never this question)."""
    fold = fold_of(cfg, repo, qid)
    dst = tmp / f"{repo}-{arm}-{model}-test{fold + 1}"
    if dst.exists():
        return dst
    shutil.copytree(prepare(cfg, repo, arm, tmp), dst)
    entries = []
    for i in range(len(folds(cfg, repo))):
        if i == fold:
            continue
        f = learned_file(cfg, repo, model, arm, i)
        if not f.exists():
            raise SystemExit(f"arm {arm}: {f} missing. Run `python -m bench learn` first.")
        entries += L.parse_lines(f.read_text(encoding="utf-8"))
    kept, _ = L.clean(entries, dst)
    (dst / L.FILE).write_text(L.render(kept), encoding="utf-8")
    add_rule(dst)
    return dst


def learn(cfg: dict, yes: bool, only: str | None) -> int:
    """One pass per fold: answer the fold's questions with the 'LEARNED:' ask; facts pile up in that fold's LEARNED.md."""
    arms = [a for a in cfg["arms"] if is_learn(cfg, a)]
    if not arms:
        print("no arm has `learn: true`"); return 0
    todo = []
    for repo in cfg["repos"]:
        for m in cfg["models"]:
            if only and m["name"] != only:
                continue
            for arm in arms:
                for i, f in enumerate(folds(cfg, repo)):
                    todo.append((repo, m, arm, i, f))
    n = sum(len(f) for *_, f in todo)
    paid_n = sum(len(f) for _, m, *__, f in todo if paid(m))
    if paid_n:
        hi = sum(len(f) * (estimate_run(per_run_tokens(cfg, arm, m["name"])[0], price_of(cfg, m)) or (0, 9e9))[1]
                 for _, m, arm, __, f in todo if paid(m))
        print(f"learning pass: {n} runs, {paid_n} paid, high estimate ${hi:.2f}")
        if not yes:
            print("Refused: paid learning runs need --yes."); return 2
        if hi > float(cfg.get("max_usd", 0)):
            print(f"Refused: ${hi:.2f} > max_usd {cfg.get('max_usd', 0)}."); return 2
    else:
        print(f"learning pass: {n} runs, $0 extra")
    out = results_file(cfg).with_name("learn.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    n_done = 0
    with tempfile.TemporaryDirectory(prefix="brieflet-learn-") as t:
        tmp = Path(t)
        for repo, m, arm, i, f in todo:
            base = prepare(cfg, repo, arm, tmp)
            wd = tmp / f"{repo}-{arm}-{m['name']}-learn{i + 1}"
            shutil.copytree(base, wd)
            (wd / L.FILE).write_text(L.render([]), encoding="utf-8")
            add_rule(wd)
            fn, price = runners.get(m["runner"]), price_of(cfg, m)
            qs = {q["id"]: q for q in questions(cfg, repo)}
            errs = 0
            for qid in f:
                row = fn(qs[qid]["text"] + L.PROMPT_SUFFIX, wd, m, price, float(cfg.get("max_usd_per_run", 1.0)))
                facts = L.from_answer(row.get("answer") or "")
                added, dropped = L.add(wd / L.FILE, wd, facts) if facts else (0, [])
                row.update(run=run_id, t=dt.datetime.now().isoformat(timespec="seconds"), repo=repo, model=m["name"],
                           arm=arm, fold=i + 1, q=qid, learned=added, dropped=dropped)
                with open(out, "a") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_done += 1
                if (wd / L.FILE).exists():
                    d = learned_file(cfg, repo, m["name"], arm, i)
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(wd / L.FILE, d)
                dashboard(cfg, f"Learning: {n_done}/{n} runs · fold{i + 1} {qid}", quiet=True)
                print(f"learn {repo} {m['name']} {arm} fold{i + 1} {qid}: +{added} facts"
                      + (f", dropped {len(dropped)}" if dropped else "") + (f"  ERROR {row['error']}" if row.get("error") else ""))
                errs = errs + 1 if row.get("error") else 0
                if errs >= 3:
                    print("learning stopped: 3 errors in a row (usage limit?). Run `bench learn` again later."); return 4
            dst = learned_file(cfg, repo, m["name"], arm, i)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(wd / L.FILE, dst)
            print(f"  → {dst}")
    notify(cfg, f"Brieflet learning pass done ({n} runs). Next: python -m bench run --resume")
    return 0


def prepare(cfg: dict, repo: str, arm: str, tmp: Path) -> Path:
    rc = cfg["repos"][repo]
    src = expand(cfg, rc["path"])
    want = str(rc.get("sha") or "")
    if len(want) == 40:
        head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if head != want:
            raise SystemExit(f"{repo}: {src} is at {head[:7] or '?'}, config pins {want[:7]}: git -C {src} checkout {want}")
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


def run(cfg: dict, yes: bool, only: str | None, resume: bool = False) -> int:
    tot = plan(cfg, only)
    max_usd = float(cfg.get("max_usd", 0))
    if tot["paid_runs"]:
        if tot["unpriced"]:
            print("\nRefused: some paid models have no price."); return 2
        if not yes:
            print("\nRefused: paid runs need --yes (after you've read the estimate above)."); return 2
        if tot["high"] > max_usd:
            print(f"\nRefused: high estimate ${tot['high']:.2f} > max_usd ${max_usd}. Lower repeats/questions or raise max_usd."); return 2
    missing = [str(learned_file(cfg, repo, m["name"], arm, i)) for repo in cfg["repos"] for m in cfg["models"]
               if not only or m["name"] == only for arm in cfg["arms"] if is_learn(cfg, arm)
               for i in range(len(folds(cfg, repo))) if not learned_file(cfg, repo, m["name"], arm, i).exists()]
    if missing:
        print(f"\nRefused: learning arm has no LEARNED.md yet ({missing[0]}). Run `python -m bench learn` first."); return 2
    reps, per_run_cap = cfg.get("repeats", 3), float(cfg.get("max_usd_per_run", 1.0))
    out = results_file(cfg)
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    spent, errors_in_a_row = 0.0, 0
    done = {(r["repo"], r["model"], r["arm"], r["q"], r["rep"]) for r in rows(cfg) if not r.get("error")} if resume else set()
    if resume:
        print(f"resume: skipping {len(done)} runs that already worked")
    n_done, todo_n = 0, max(0, tot["runs"] - sum(len(qs) for _, __, arm, qs in matrix(cfg, only) if is_learn(cfg, arm))
                            - len(done))
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
                            if (repo, m["name"], arm, q["id"], r) in done:
                                continue
                            if paid(m):
                                tok, _ = per_run_tokens(cfg, arm, m["name"])
                                nxt = estimate_run(tok, price)[1]
                                if spent + min(nxt, per_run_cap) > max_usd:
                                    print(f"STOP: spent ${spent:.2f}, next run could pass max_usd ${max_usd}."); return 3
                            wd = (prepare_learn(cfg, repo, m["name"], arm, q["id"], tmp) if is_learn(cfg, arm)
                                  else prepare(cfg, repo, arm, tmp))
                            row = fn(q["text"], wd, m, price, per_run_cap)
                            if paid(m):
                                spent += row.get("cost_usd") or 0
                            row.update(run=run_id, t=dt.datetime.now().isoformat(timespec="seconds"), repo=repo,
                                       sha=cfg["repos"][repo].get("sha"), model=m["name"], runner=m["runner"],
                                       model_id=m["model"], arm=arm, q=q["id"], qtype=q.get("type"), rep=r,
                                       question=q["text"])
                            with open(out, "a") as fh:
                                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                            n_done += 1
                            dashboard(cfg, f"Running: {n_done}/{todo_n} runs · {arm} {q['id']}", quiet=True)
                            errors_in_a_row = errors_in_a_row + 1 if row.get("error") else 0
                            tin = row["input_tokens"] + row["cache_read"] + row["cache_write"]
                            print(f"{repo} {m['name']} {q['id']} #{r} {arm:14} in={tin:>8,} out={row['output_tokens']:>6,} "
                                  f"{row['secs']:>6}s" + (f"  ERROR {row['error']}" if row.get("error") else ""))
                            if errors_in_a_row >= 3:
                                msg = (f"Brieflet bench stopped: 3 errors in a row (usage limit?). Last: {row['error']}. "
                                       "Run again later with --resume.")
                                print(msg)
                                if cfg.get("notify_cmd") and shutil.which(cfg["notify_cmd"]):
                                    subprocess.run([cfg["notify_cmd"], msg[:300]], check=False, timeout=30)
                                return 4
    msg = f"Brieflet bench {run_id} done: paid spend ≈ ${spent:.2f}. Rows → {out}"
    print("\n" + msg)
    if cfg.get("notify_cmd") and shutil.which(cfg["notify_cmd"]):
        subprocess.run([cfg["notify_cmd"], msg], check=False, timeout=30)
    return 0


def judge_file(cfg: dict) -> Path:
    return results_file(cfg).with_name("judge.jsonl")


def verdicts(cfg: dict) -> dict:
    f = judge_file(cfg)
    out = {}
    if f.exists():
        for l in open(f):
            if l.strip():
                v = json.loads(l)
                out[v["key"]] = v
    return out


def row_key(r: dict) -> str:
    return f'{r["run"]}|{r["repo"]}|{r["model"]}|{r["arm"]}|{r["q"]}|{r["rep"]}'


def notify(cfg: dict, msg: str) -> None:
    if cfg.get("notify_cmd") and shutil.which(cfg["notify_cmd"]):
        subprocess.run([cfg["notify_cmd"], msg[:300]], check=False, timeout=30)


def judge(cfg: dict, yes: bool) -> int:
    jc = cfg.get("judge") or {"runner": "claude_code", "model": "opus"}
    done = {k for k, v in verdicts(cfg).items() if v.get("score") is not None}  # failed ones are retried
    todo = []
    for r in rows(cfg):
        if r.get("error") or row_key(r) in done:
            continue
        refs = J.refs_for(expand(cfg, cfg["repos"][r["repo"]]["questions"])).get(r["q"])
        if refs:
            todo.append((r, refs))
    if not todo:
        print("nothing to judge"); return 0
    chars = sum(len(J.SYSTEM) + len(J.prompt(r["question"], refs, r.get("answer") or "")) for r, refs in todo)
    if jc.get("runner", "claude_code") == "claude_code":
        print(f"{len(todo)} answers to judge with Claude Code ({jc.get('model', 'opus')}) on your login: $0 extra.")
    else:
        p = cfg["_prices"]["anthropic"].get(jc["model"])
        if not p:
            print(f"Refused: no price for judge model {jc['model']}"); return 2
        est = (chars / J.CHARS_PER_TOKEN * p["input"] + len(todo) * 600 * p["output"]) / 1e6
        print(f"{len(todo)} answers to judge with {jc['model']} via API: estimate ${est:.2f}.")
        if not yes:
            print("Refused: paid judge needs --yes."); return 2
        if est > float(cfg.get("max_usd", 0)):
            print(f"Refused: estimate > max_usd ${cfg.get('max_usd', 0)}."); return 2
    fails = 0
    with open(judge_file(cfg), "a") as fh:
        for i, (r, refs) in enumerate(todo, 1):
            raw, use = J.ask(jc, J.prompt(r["question"], refs, r.get("answer") or ""))
            v = J.parse(raw)
            rec = {"key": row_key(r), "q": r["q"], "arm": r["arm"], "model": r["model"], "repo": r["repo"],
                   "judge": jc.get("model"), "verdict": v, "score": J.score(len(refs["must"]), v) if v else None, **use}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{i}/{len(todo)} {r['q']} {r['arm']:14} score={rec['score']}")
            dashboard(cfg, f"Judging: {i}/{len(todo)} answers", quiet=True)
            fails = fails + 1 if rec["score"] is None else 0
            if fails >= 3:
                msg = "Brieflet judge stopped: 3 failures in a row (usage limit?). Run judge again later, it continues."
                print(msg)
                notify(cfg, msg)
                return 4
    notify(cfg, f"Brieflet judge done: {len(todo)} answers scored. Dashboard updated.")
    return 0


def report(cfg: dict) -> int:
    rs = [r for r in rows(cfg) if not r.get("error")]
    if not rs:
        print("no results yet"); return 0
    med = lambda xs: st.median(xs) if xs else 0
    vd = verdicts(cfg)
    L = ["| repo | model | arm | input tokens (sum of q medians) | vs none | seconds | USD (API price) | ok/all "
         "| quality 0-3 (mean) | good answers (≥2) | input tokens per good answer |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    allrows = rows(cfg)
    for repo in sorted({r["repo"] for r in rs}):
        for model in sorted({r["model"] for r in rs if r["repo"] == repo}):
            base = None
            have = [{r["q"] for r in rs if r["repo"] == repo and r["model"] == model and r["arm"] == a} for a in cfg["arms"]]
            common = sorted(set.intersection(*[h for h in have if h])) if any(have) else []
            print(f"{repo} / {model}: tokens, seconds and USD are summed over the {len(common)} questions every setup answered: "
                  f"{', '.join(common)}")
            for arm in cfg["arms"]:
                g = [r for r in rs if r["repo"] == repo and r["model"] == model and r["arm"] == arm]
                if not g:
                    continue
                qs = common
                tin = sum(med([r["input_tokens"] + r["cache_read"] + r["cache_write"] for r in g if r["q"] == q]) for q in qs)
                secs = sum(med([r["secs"] for r in g if r["q"] == q]) for q in qs)
                usd = sum(med([r.get("cost_usd") or 0 for r in g if r["q"] == q]) for q in qs)
                if arm == "none":
                    base = tin
                vs = f"{(tin / base - 1) * 100:+.0f}%" if base and arm != "none" else ""
                n_all = sum(1 for r in allrows if r["repo"] == repo and r["model"] == model and r["arm"] == arm)
                sc = [vd[row_key(r)]["score"] for r in g if row_key(r) in vd and vd[row_key(r)]["score"] is not None]
                good = sum(1 for x in sc if x >= 2)
                tok_all = sum(r["input_tokens"] + r["cache_read"] + r["cache_write"] for r in g if row_key(r) in vd)
                qual = f"{st.mean(sc):.2f} (n={len(sc)})" if sc else "–"
                per_good = f"{tok_all / good:,.0f}" if good else "–"
                L.append(f"| {repo} | {model} | {arm} | {tin:,.0f} | {vs} | {secs:.0f} | {usd:.3f} | {len(g)}/{n_all} "
                         f"| {qual} | {good}/{len(sc)} | {per_good} |")
    print("\n".join(L))
    if not vd:
        print("\nNo quality scores yet: run `judge`. Fewer tokens with a worse answer is not a win.")
    return 0


def dashboard(cfg: dict, status: str = "", quiet: bool = False) -> None:
    """Rebuilt after EVERY row (run / learn / judge); the page reloads itself when it changes (geolinux serves :8097)."""
    from .dashboard import build
    out = results_file(cfg).with_name("dashboard.html")
    try:
        html = build(cfg, rows(cfg), verdicts(cfg), row_key, expand, status, results_file(cfg).parent / "learned")
        tmp = out.with_suffix(".tmp")
        tmp.write_text(html, encoding="utf-8")
        tmp.replace(out)  # atomic: the page never sees a half-written file
        if not quiet:
            print(f"dashboard: {out}")
    except Exception as e:  # never let the page break a finished run
        print(f"dashboard not rebuilt: {e}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bench")
    ap.add_argument("cmd", choices=["plan", "learn", "run", "judge", "report", "dashboard"])
    ap.add_argument("-c", "--config", default="bench.yaml")
    ap.add_argument("--yes", action="store_true", help="allow paid runs (after reading `plan`)")
    ap.add_argument("--only", help="only this model name from the config")
    ap.add_argument("--resume", action="store_true", help="skip runs that already worked (after a usage limit)")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up in a nohup log right away
    cfg = load(a.config)
    if a.cmd == "plan":
        plan(cfg, a.only); return 0
    if a.cmd == "learn":
        rc = learn(cfg, a.yes, a.only)
        dashboard(cfg)
        return rc
    if a.cmd == "run":
        rc = run(cfg, a.yes, a.only, a.resume)
        dashboard(cfg)
        return rc
    if a.cmd == "judge":
        rc = judge(cfg, a.yes)
        dashboard(cfg)
        return rc
    if a.cmd == "dashboard":
        dashboard(cfg)
        return 0
    return report(cfg)


if __name__ == "__main__":
    sys.exit(main())
