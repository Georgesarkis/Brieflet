"""Controller for `brieflet init`: plan → run the use case → present → write the files."""
from __future__ import annotations

from dataclasses import dataclass

from ..application.generate_brief import BriefPlan, GenerateBrief
from ..application.ports import Folder
from .brief_presenter import present


@dataclass
class BriefResult:
    files: list[str]
    notes: list[str]
    calls: list[dict]

    def as_dict(self) -> dict:
        return {"files": self.files, "notes": self.notes, "calls": self.calls}


class BriefController:
    def __init__(self, use_case: GenerateBrief, target: Folder, footer: bool):
        self.use_case, self.target, self.footer = use_case, target, footer

    def plan(self) -> BriefPlan:
        return self.use_case.plan()

    def run(self, plan: BriefPlan) -> BriefResult:
        brief = self.use_case.run(plan)
        files = present(brief, self.footer)
        for rel, txt in files.items():
            self.target.write(rel, txt)
        return BriefResult(sorted(files), brief.notes, self.use_case.model.calls)
