"""Use case: the learning pass. Per fold, answer its questions with the LEARNED: ask; facts pile up in that fold's
LEARNED.md, which `bench run` later gives to the OTHER folds' questions only."""
from __future__ import annotations

import datetime as dt

from brieflet.application.prompts import LEARNED_ASK

from ..domain.pricing import estimate_run, is_paid
from .config import BenchConfig
from .outcome import Outcome
from .plan_benchmark import tokens_per_run
from .ports import Log, Notifier, OpenWorkspaces, Progress, ResultsStore, RunnerFactory

ERRORS_TO_STOP = 3
NO_PRICE_USD = 9e9   # a paid model without a price can never pass the budget


class LearningPass:
    def __init__(self, cfg: BenchConfig, store: ResultsStore, runner_for: RunnerFactory, open_workspaces: OpenWorkspaces,
                 notifier: Notifier, progress: Progress, log: Log = print):
        self.cfg, self.store, self.runner_for, self.open_workspaces = cfg, store, runner_for, open_workspaces
        self.notifier, self.progress, self.log = notifier, progress, log

    def execute(self, yes: bool, only: str | None = None) -> Outcome:
        arms = [a for a in self.cfg.arms if self.cfg.is_learn(a)]
        if not arms:
            self.log("no arm has `learn: true`")
            return Outcome.OK
        todo = [(repo, m, arm, i, f) for repo in self.cfg.repos for m in self.cfg.models_for(only) for arm in arms
                for i, f in enumerate(self.cfg.folds(repo))]
        self.total = sum(len(f) for *_, f in todo)
        if not self._money_gate(todo, yes):
            return Outcome.REFUSED
        self.run_id, self.n_done = dt.datetime.now().strftime("%Y%m%d-%H%M%S"), 0
        with self.open_workspaces() as ws:
            for repo, m, arm, i, fold in todo:
                if self._fold(ws, repo, m, arm, i, fold) is Outcome.ERROR_STOP:
                    return Outcome.ERROR_STOP
        self.notifier.send(f"Brieflet learning pass done ({self.total} runs). Next: python -m bench run --resume")
        return Outcome.OK

    def _money_gate(self, todo: list, yes: bool) -> bool:
        paid = [(m, arm, f) for _, m, arm, __, f in todo if is_paid(m)]
        if not paid:
            self.log(f"learning pass: {self.total} runs, $0 extra")
            return True
        hi = sum(len(f) * (estimate_run(tokens_per_run(self.cfg, self.store, arm, m["name"])[0], self.cfg.price(m))
                           or (0, NO_PRICE_USD))[1] for m, arm, f in paid)
        self.log(f"learning pass: {self.total} runs, {sum(len(f) for *_, f in paid)} paid, high estimate ${hi:.2f}")
        if not yes:
            self.log("Refused: paid learning runs need --yes.")
            return False
        if hi > self.cfg.max_usd:
            self.log(f"Refused: ${hi:.2f} > max_usd {self.cfg.max_usd}.")
            return False
        return True

    def _fold(self, ws, repo: str, m: dict, arm: str, i: int, fold: list[str]) -> Outcome:
        wd = ws.learning(repo, m["name"], arm, i)
        qs = {q["id"]: q for q in self.cfg.questions[repo]}
        errors = 0
        for qid in fold:
            row = self.runner_for(m["runner"])(qs[qid]["text"] + LEARNED_ASK, wd, m, self.cfg.price(m), self.cfg.max_usd_per_run)
            added, dropped = ws.add_learned(wd, row.get("answer") or "")
            row.update(run=self.run_id, t=dt.datetime.now().isoformat(timespec="seconds"), repo=repo, model=m["name"],
                       arm=arm, fold=i + 1, q=qid, learned=added, dropped=dropped)
            self.store.add_learn(row)
            self.n_done += 1
            self._save(ws, wd, repo, m, arm, i)
            self.progress(f"Learning: {self.n_done}/{self.total} runs · fold{i + 1} {qid}")
            self.log(f"learn {repo} {m['name']} {arm} fold{i + 1} {qid}: +{added} facts"
                     + (f", dropped {len(dropped)}" if dropped else "") + (f"  ERROR {row['error']}" if row.get("error") else ""))
            errors = errors + 1 if row.get("error") else 0
            if errors >= ERRORS_TO_STOP:
                self.log("learning stopped: 3 errors in a row (usage limit?). Run `bench learn` again later.")
                return Outcome.ERROR_STOP
        self.log(f"  → {self._save(ws, wd, repo, m, arm, i)}")
        return Outcome.OK

    def _save(self, ws, wd, repo: str, m: dict, arm: str, i: int):
        text = ws.learned_text(wd)
        return self.store.save_learned(repo, m["name"], arm, i, text) if text is not None else None
