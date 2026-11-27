"""Use case: generate a repo's brief (labels, AI_CONTEXT, decision records, LEARNED.md) from code + a model.

Returns a Brief (data). Turning it into Markdown is the presentation layer's job; writing files is infrastructure's.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..domain import learned
from ..domain.components import ComponentGraph
from ..domain.decisions import MAX_RECORDS, DecisionCandidate, DecisionRecord
from ..domain.learned import LearnedFact
from . import prompts as P
from .model_answers import ContextDraft, context_from, decision_from, labels_from
from .ports import SMALL, WRITE, ComponentScanner, DecisionScanner, Folder, LanguageModel, ModelError, RepoSnapshot


class NoComponentsFound(Exception):
    """The repo has no component model this version can read (today: no .NET Aspire AppHost)."""


@dataclass
class BriefPlan:
    graph: ComponentGraph
    candidates: list[DecisionCandidate]
    calls: list[tuple[str, int, int]]          # (role, prompt chars, max output tokens), for the cost estimate


@dataclass
class Brief:
    graph: ComponentGraph
    labels: dict[str, str]
    context: ContextDraft
    decisions: list[DecisionRecord]
    learned: list[LearnedFact]
    write_claude_md: bool
    notes: list[str]


class GenerateBrief:
    def __init__(self, snapshot: RepoSnapshot, components: ComponentScanner, decisions: DecisionScanner,
                 model: LanguageModel, repo: Folder, writes_into_repo: bool, log: Callable[[str], None] = print):
        self.snapshot, self.components, self.decisions = snapshot, components, decisions
        self.model, self.repo, self.writes_into_repo, self.log = model, repo, writes_into_repo, log
        self.notes: list[str] = []

    def plan(self) -> BriefPlan:
        """What would run, without calling a model."""
        graph = self.components.scan(self.snapshot)
        if graph.is_empty:
            raise NoComponentsFound("No .NET Aspire AppHost found: Brieflet's component parser supports Aspire repos only (for now).")
        cands = self.decisions.scan(self.snapshot, graph)[:MAX_RECORDS]
        calls = [(SMALL, len(P.label_prompt(graph)) + len(P.LABEL_SYSTEM), P.MAX_OUT["labels"]),
                 (WRITE, len(P.context_prompt(graph, {}, self.snapshot.files)) + len(P.CONTEXT_SYSTEM), P.MAX_OUT["context"])]
        calls += [(WRITE, len(P.decision_prompt(c)) + len(P.DECISION_SYSTEM), P.MAX_OUT["decision"]) for c in cands]
        return BriefPlan(graph, cands, calls)

    def run(self, plan: BriefPlan) -> Brief:
        graph = plan.graph
        self.log(f"labels ({self.model.small}) …")
        labels = labels_from(self._ask(SMALL, P.LABEL_SYSTEM, P.label_prompt(graph), P.MAX_OUT["labels"]), graph)
        self.log(f"AI_CONTEXT ({self.model.write}) …")
        answer = self._ask(WRITE, P.CONTEXT_SYSTEM, P.context_prompt(graph, labels, self.snapshot.files), P.MAX_OUT["context"])
        context = context_from(answer, self._path_in_repo, self.notes)
        self.log(f"{len(plan.candidates)} decision records ({self.model.write}) …")
        records = self._decision_records(plan.candidates)
        facts = self._learned_facts()
        write_claude = not self.writes_into_repo or not self.repo.exists("CLAUDE.md")
        return Brief(graph, labels, context, records, facts, write_claude, self.notes)

    # ---------------------------------------------------------------- steps
    def _ask(self, role: str, system: str, prompt: str, max_out: int) -> dict | None:
        try:
            return self.model.ask_json(role, system, prompt, max_out)[0]
        except ModelError as e:
            self.notes.append(f"model call failed ({role}): {e}")
            return None

    def _path_in_repo(self, p: str) -> bool:
        return self.snapshot.has(p) or self.snapshot.has_dir(p)

    def _decision_records(self, cands: list[DecisionCandidate]) -> list[DecisionRecord]:
        out: list[DecisionRecord] = []
        for c in cands:
            answer = self._ask(WRITE, P.DECISION_SYSTEM, P.decision_prompt(c), P.MAX_OUT["decision"])
            rec, problem = decision_from(answer, c, f"{len(out) + 1:04d}")
            if problem:
                self.notes.append(problem)
                continue
            out.append(rec)
        return out

    def _learned_facts(self) -> list[LearnedFact]:
        """Keep what assistants added to LEARNED.md, drop lines whose files are gone."""
        old = learned.parse_facts(self.repo.read(learned.FILE) or "")
        kept, dropped = learned.prune(old, lambda p: self.repo.exists(p.split(":")[0].split("#")[0]))
        self.notes += [f"LEARNED.md dropped: {d}" for d in dropped]
        return kept
