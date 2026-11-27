"""Interfaces the use cases depend on. Infrastructure implements them; tests fake them.

Same idea as C# interfaces in an Application project: the use case never imports git, HTTP clients or SDKs.
"""
from __future__ import annotations

from typing import Protocol

from ..domain.components import ComponentGraph
from ..domain.decisions import DecisionCandidate

SMALL, WRITE = "small", "write"   # model roles: cheap labels vs. prose


class ModelError(RuntimeError):
    """The model backend failed (network, HTTP status, refusal). A bad *answer* is not an error: it returns None."""


class RepoUnreadable(RuntimeError):
    """The repo can't be read (not a git repo, unknown revision)."""


class RepoSnapshot(Protocol):
    """Read-only view of a repo at one commit."""
    files: list[str]

    def has(self, path: str) -> bool: ...
    def has_dir(self, path: str) -> bool: ...
    def read(self, path: str) -> str | None: ...
    def commit_that_added(self, path: str) -> str | None: ...   # "<sha> <date> <subject>"


class ComponentScanner(Protocol):
    def scan(self, snapshot: RepoSnapshot) -> ComponentGraph: ...


class DecisionScanner(Protocol):
    def scan(self, snapshot: RepoSnapshot, graph: ComponentGraph) -> list[DecisionCandidate]: ...


class Folder(Protocol):
    """A folder on disk (the repo's working tree, or the --out folder)."""
    def exists(self, rel: str) -> bool: ...
    def read(self, rel: str) -> str | None: ...
    def write(self, rel: str, text: str) -> None: ...


class LanguageModel(Protocol):
    small: str
    write: str
    paid: bool
    calls: list[dict]

    def ask_json(self, role: str, system: str, prompt: str, max_out: int) -> tuple[dict | None, str]: ...
    def estimate_usd(self, planned: list[tuple[str, int, int]]) -> float | None: ...
