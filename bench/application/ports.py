"""Interfaces the bench use cases depend on; infrastructure implements them, tests fake them."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import ContextManager, Protocol

# Answers one question inside one arm's working copy → result row (see domain/results.py).
Runner = Callable[[str, Path, dict, "dict | None", float], dict]
RunnerFactory = Callable[[str], Runner]
Progress = Callable[[str], None]   # live status line (the dashboard shows it)
Log = Callable[[str], None]


class ResultsStore(Protocol):
    def runs(self) -> list[dict]: ...
    def add_run(self, row: dict) -> None: ...
    def add_learn(self, row: dict) -> None: ...
    def verdicts(self) -> dict[str, dict]: ...
    def add_verdict(self, rec: dict) -> None: ...
    def learned_file(self, repo: str, model: str, arm: str, fold: int) -> Path: ...
    def save_learned(self, repo: str, model: str, arm: str, fold: int, text: str) -> Path: ...
    @property
    def runs_path(self) -> Path: ...


class Workspaces(Protocol):
    """Working copies the readers answer in: repo at the pinned commit + the arm's docs."""
    def arm(self, repo: str, arm: str) -> Path: ...
    def learning(self, repo: str, model: str, arm: str, fold: int) -> Path: ...
    def measured_learn(self, repo: str, model: str, arm: str, qid: str) -> Path: ...
    def add_learned(self, workdir: Path, answer: str) -> tuple[int, list[str]]: ...   # → (facts added, dropped reasons)
    def learned_text(self, workdir: Path) -> str | None: ...


OpenWorkspaces = Callable[[], ContextManager[Workspaces]]   # one temp area per command, removed after


class JudgeClient(Protocol):
    def ask(self, judge: dict, text: str) -> tuple[str, dict]: ...   # → (raw reply, usage)


class Notifier(Protocol):
    def send(self, msg: str) -> None: ...
