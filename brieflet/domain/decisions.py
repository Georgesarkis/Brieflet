"""Architecture decision records (ADRs): what the code shows (candidate) and what a model wrote (record)."""
from __future__ import annotations

from dataclasses import dataclass, field

STATUS_INFERRED = "Inferred — needs human confirm"
MAX_RECORDS = 10
CONFIDENCE_LEVELS = ("low", "medium", "high")


@dataclass(frozen=True)
class DecisionSignal:
    """One kind of decision the code can show. pattern=None means 'the AppHost itself is the evidence'."""
    key: str
    type: str
    reason: str
    pattern: str | None


@dataclass
class DecisionCandidate:
    key: str
    type: str
    reason: str
    evidence: list[str]
    excerpt: str = ""
    commits: list[str] = field(default_factory=list)  # "<sha> <date> <subject>"


@dataclass
class DecisionRecord:
    number: str                    # "0001"
    title: str
    slug: str
    type: str
    confidence: str
    context: str
    decision: str
    consequences: str
    candidate: DecisionCandidate

    @property
    def path(self) -> str:
        return f"docs/decisions/{self.number}-{self.slug}.md"
