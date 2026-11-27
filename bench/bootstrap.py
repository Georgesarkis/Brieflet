"""Composition root (like Program.cs): the only place that picks concrete classes for the bench's ports."""
from __future__ import annotations

from pathlib import Path

import yaml

from .application.judge_answers import SYSTEM as JUDGE_SYSTEM
from .application.judge_answers import JudgeAnswers
from .application.learning_pass import LearningPass
from .application.plan_benchmark import PlanBenchmark
from .application.ports import JudgeClient, RunnerFactory
from .application.run_benchmark import RunBenchmark
from .infrastructure.config_loader import load
from .infrastructure.judge_clients import JudgeClients
from .infrastructure.notifier import CommandNotifier
from .infrastructure.results_store import JsonlResults
from .infrastructure.runners import runner_for as real_runners
from .infrastructure.workspaces import SetupError, opener
from .presentation import dashboard

__all__ = ["BenchApp", "SetupError"]


class BenchApp:
    """Builds the use cases for one bench.yaml. runner_for / judge: swap in fakes (tests)."""

    def __init__(self, config_path: str, runner_for: RunnerFactory | None = None, judge: JudgeClient | None = None):
        self.cfg = load(config_path)
        self.cfg_path = Path(config_path).resolve()
        self.store = JsonlResults(self.cfg.results_dir)
        self.notifier = CommandNotifier(self.cfg.data.get("notify_cmd"))
        self.runners = runner_for or real_runners
        self.judge_client = judge or JudgeClients(JUDGE_SYSTEM)

    def live(self, status: str) -> None:
        dashboard.publish(self.cfg, self.store, status, quiet=True, siblings=self.siblings)

    def publish_dashboard(self) -> None:
        dashboard.publish(self.cfg, self.store, siblings=self.siblings)

    def siblings(self) -> list[tuple]:
        """(config, results) for every bench config next to this one that writes into the same results root."""
        out = []
        for f in sorted(self.cfg.dir.glob("*.yaml")):
            try:
                if f.resolve() == self.cfg_path:
                    c = self.cfg
                else:
                    data = yaml.safe_load(open(f, encoding="utf-8")) or {}
                    if not isinstance(data, dict) or "repos" not in data or "results" not in data:
                        continue
                    c = load(f)
            except Exception:  # noqa: BLE001 - a broken neighbour config must not break this page
                continue
            if c.results_dir.parent == self.cfg.results_dir.parent and (c.results_dir / "runs.jsonl").exists():
                out.append((c, self.store if c is self.cfg else JsonlResults(c.results_dir)))
        return out

    def plan(self) -> PlanBenchmark:
        return PlanBenchmark(self.cfg, self.store)

    def run(self) -> RunBenchmark:
        return RunBenchmark(self.cfg, self.store, self.runners, opener(self.cfg, self.store, "brieflet-bench-"),
                            self.notifier, self.live)

    def learn(self) -> LearningPass:
        return LearningPass(self.cfg, self.store, self.runners, opener(self.cfg, self.store, "brieflet-learn-"),
                            self.notifier, self.live)

    def judge(self) -> JudgeAnswers:
        return JudgeAnswers(self.cfg, self.store, self.judge_client, self.notifier, self.live)
