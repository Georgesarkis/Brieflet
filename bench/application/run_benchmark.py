"""Use case: answer every question in every arm, with the money gate, a live budget stop and --resume."""
from __future__ import annotations

import datetime as dt

from ..domain.pricing import estimate_run, is_paid
from ..domain.results import input_tokens
from .config import BenchConfig
from .outcome import Outcome
from .plan_benchmark import BenchPlan, tokens_per_run
from .ports import Log, Notifier, OpenWorkspaces, Progress, ResultsStore, RunnerFactory

ERRORS_TO_STOP = 3


def money_gate(plan: BenchPlan, yes: bool, log: Log) -> bool:
    """True when paid runs may start: every paid model priced, --yes given, high estimate within max_usd."""
    t = plan.totals
    if not t.paid_runs:
        return True
    if t.unpriced:
        log("\nRefused: some paid models have no price.")
    elif not yes:
        log("\nRefused: paid runs need --yes (after you've read the estimate above).")
    elif t.high > plan.max_usd:
        log(f"\nRefused: high estimate ${t.high:.2f} > max_usd ${plan.max_usd}. Lower repeats/questions or raise max_usd.")
    else:
        return True
    return False


class RunBenchmark:
    def __init__(self, cfg: BenchConfig, store: ResultsStore, runner_for: RunnerFactory, open_workspaces: OpenWorkspaces,
                 notifier: Notifier, progress: Progress, log: Log = print):
        self.cfg, self.store, self.runner_for, self.open_workspaces = cfg, store, runner_for, open_workspaces
        self.notifier, self.progress, self.log = notifier, progress, log

    def execute(self, plan: BenchPlan, yes: bool, only: str | None = None, resume: bool = False) -> Outcome:
        if not money_gate(plan, yes, self.log):
            return Outcome.REFUSED
        if missing := self._missing_learned(only):
            self.log(f"\nRefused: learning arm has no LEARNED.md yet ({missing[0]}). Run `python -m bench learn` first.")
            return Outcome.REFUSED
        done = {(r["repo"], r["model"], r["arm"], r["q"], r["rep"]) for r in self.store.runs() if not r.get("error")} if resume else set()
        if resume:
            self.log(f"resume: skipping {len(done)} runs that already worked")
        self.run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.spent, self.errors, self.n_done = 0.0, 0, 0
        self.todo = max(0, plan.totals.runs - plan.totals.learn_runs - len(done))
        with self.open_workspaces() as ws:
            for repo, m, q, rep, arm in self._cells(only):
                if (repo, m["name"], arm, q["id"], rep) in done:
                    continue
                if self._over_budget(m, arm):
                    self.log(f"STOP: spent ${self.spent:.2f}, next run could pass max_usd ${self.cfg.max_usd}.")
                    return Outcome.BUDGET_STOP
                wd = ws.measured_learn(repo, m["name"], arm, q["id"]) if self.cfg.is_learn(arm) else ws.arm(repo, arm)
                row = self._answer(repo, m, q, rep, arm, wd)
                if self.errors >= ERRORS_TO_STOP:
                    msg = (f"Brieflet bench stopped: 3 errors in a row (usage limit?). Last: {row['error']}. "
                           "Run again later with --resume.")
                    self.log(msg)
                    self.notifier.send(msg)
                    return Outcome.ERROR_STOP
        msg = f"Brieflet bench {self.run_id} done: paid spend ≈ ${self.spent:.2f}. Rows → {self.store.runs_path}"
        self.log("\n" + msg)
        self.notifier.send(msg)
        return Outcome.OK

    def _cells(self, only: str | None):
        """Arms innermost (interleaved), so time-of-day and cache effects hit all arms alike."""
        for repo in self.cfg.repos:
            for m in self.cfg.models_for(only):
                for q in self.cfg.questions[repo]:
                    for rep in range(1, self.cfg.repeats + 1):
                        for arm in self.cfg.arms:
                            yield repo, m, q, rep, arm

    def _missing_learned(self, only: str | None) -> list[str]:
        return [str(f) for repo in self.cfg.repos for m in self.cfg.models_for(only) for arm in self.cfg.arms
                if self.cfg.is_learn(arm) for i in range(len(self.cfg.folds(repo)))
                if not (f := self.store.learned_file(repo, m["name"], arm, i)).exists()]

    def _over_budget(self, m: dict, arm: str) -> bool:
        if not is_paid(m):
            return False
        nxt = estimate_run(tokens_per_run(self.cfg, self.store, arm, m["name"])[0], self.cfg.price(m))[1]
        return self.spent + min(nxt, self.cfg.max_usd_per_run) > self.cfg.max_usd

    def _answer(self, repo: str, m: dict, q: dict, rep: int, arm: str, wd) -> dict:
        row = self.runner_for(m["runner"])(q["text"], wd, m, self.cfg.price(m), self.cfg.max_usd_per_run)
        if is_paid(m):
            self.spent += row.get("cost_usd") or 0
        row.update(run=self.run_id, t=dt.datetime.now().isoformat(timespec="seconds"), repo=repo,
                   sha=self.cfg.repos[repo].get("sha"), model=m["name"], runner=m["runner"], model_id=m["model"],
                   arm=arm, q=q["id"], qtype=q.get("type"), rep=rep, question=q["text"])
        self.store.add_run(row)
        self.n_done += 1
        self.progress(f"Running: {self.n_done}/{self.todo} runs · {arm} {q['id']}")
        self.errors = self.errors + 1 if row.get("error") else 0
        self.log(f"{repo} {m['name']} {q['id']} #{rep} {arm:14} in={input_tokens(row):>8,} out={row['output_tokens']:>6,} "
                 f"{row['secs']:>6}s" + (f"  ERROR {row['error']}" if row.get("error") else ""))
        return row
