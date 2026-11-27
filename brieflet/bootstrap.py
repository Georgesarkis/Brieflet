"""Composition root (like Program.cs): the only place that picks concrete classes for the ports."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .application.generate_brief import GenerateBrief
from .application.ports import LanguageModel
from .infrastructure.dotnet.aspire_scanner import AspireScanner
from .infrastructure.dotnet.decision_scanner import DotnetDecisionScanner
from .infrastructure.folder import DiskFolder
from .infrastructure.git_snapshot import GitSnapshot
from .infrastructure.llm.gateway import ModelGateway
from .presentation.brief_controller import BriefController
from .presentation.views.footer import footer_from_env


def brief_controller(repo: Path, model: LanguageModel, out: Path | None = None, rev: str = "HEAD",
                     footer: bool | None = None, log: Callable[[str], None] = print) -> BriefController:
    repo = Path(repo).resolve()
    out = Path(out).resolve() if out else repo
    use_case = GenerateBrief(GitSnapshot(repo, rev), AspireScanner(), DotnetDecisionScanner(), model,
                             DiskFolder(repo), writes_into_repo=out == repo, log=log)
    return BriefController(use_case, DiskFolder(out), footer_from_env() if footer is None else footer)


def language_model(backend: str, small: str | None = None, write: str | None = None) -> LanguageModel:
    """Raises ModelError for an unknown backend or missing model names."""
    return ModelGateway(backend, small, write)
