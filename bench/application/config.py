"""BenchConfig: the loaded bench.yaml (+ prices, questions, reference points). In memory, no file reads here."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..domain import folds as F
from ..domain.pricing import price_of

DEFAULT_PRIOR = {"input": 80000, "output": 2000}


@dataclass
class BenchConfig:
    data: dict                                   # bench.yaml as written
    dir: Path                                    # folder of bench.yaml: relative paths start here
    prices: dict
    questions: dict[str, list[dict]] = field(default_factory=dict)   # repo → questions
    refs: dict[str, dict] = field(default_factory=dict)              # repo → {question id: {must, nice}}

    # ---------------------------------------------------------------- plain settings
    @property
    def repos(self) -> dict:
        return self.data["repos"]

    @property
    def arms(self) -> list[str]:
        return list(self.data["arms"])

    @property
    def models(self) -> list[dict]:
        return self.data["models"]

    @property
    def repeats(self) -> int:
        return self.data.get("repeats", 3)

    @property
    def max_usd(self) -> float:
        return float(self.data.get("max_usd", 0))

    @property
    def max_usd_per_run(self) -> float:
        return float(self.data.get("max_usd_per_run", 1.0))

    @property
    def judge(self) -> dict:
        """bench.yaml `judge:` block ({runner, model, billing?}). There is no default judge: it needs a plugin."""
        return self.data.get("judge") or {}

    def arm(self, name: str) -> dict:
        return self.data["arms"][name] or {}

    def is_learn(self, arm: str) -> bool:
        return bool(self.arm(arm).get("learn"))

    def models_for(self, only: str | None) -> list[dict]:
        return [m for m in self.models if not only or m["name"] == only]

    def price(self, model: dict) -> dict | None:
        return price_of(self.prices, model)

    def prior_tokens(self, arm: str) -> dict:
        pri = self.data.get("prior_tokens", {})
        return pri.get(arm) or pri.get("default") or DEFAULT_PRIOR

    # ---------------------------------------------------------------- paths
    def path(self, s: str, repo: str = "") -> Path:
        """{artifacts} and {repo} filled in, ~ expanded, relative to the config folder."""
        s = s.replace("{artifacts}", str(self.data.get("artifacts", ""))).replace("{repo}", repo)
        p = Path(os.path.expanduser(s))
        return p if p.is_absolute() else self.dir / p

    @property
    def results_dir(self) -> Path:
        return self.path(self.data.get("results", "results"))

    def artifacts_dir(self, repo: str) -> Path:
        return self.path(str(self.data.get("artifacts", "artifacts")) + "/" + repo)

    # ---------------------------------------------------------------- questions + folds
    def matrix(self, only: str | None):
        """(repo, model, arm, questions) for every cell of the benchmark."""
        for repo in self.repos:
            for m in self.models_for(only):
                for arm in self.arms:
                    yield repo, m, arm, self.questions[repo]

    def folds(self, repo: str) -> list[list[str]]:
        return F.split([q["id"] for q in self.questions[repo]], int((self.data.get("learn") or {}).get("folds", 2)))

    def fold_of(self, repo: str, qid: str) -> int:
        return F.fold_of(self.folds(repo), qid)
