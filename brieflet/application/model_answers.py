"""Turn a model's JSON answer into checked data. Anything unverifiable is dropped, with a note saying why."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..domain.components import ComponentGraph
from ..domain.decisions import CONFIDENCE_LEVELS, DecisionCandidate, DecisionRecord
from ..domain.model_text import box_label, looks_secret, plain, slug

MAX_WHERE, MAX_TALK = 12, 8


@dataclass
class ContextDraft:
    overview: str = ""
    how_they_talk: list[str] = field(default_factory=list)
    where: list[tuple[str, list[str]]] = field(default_factory=list)   # (topic, verified paths)


def labels_from(answer: dict | None, graph: ComponentGraph) -> dict[str, str]:
    """{component id: label}; a box without a usable label falls back to its kind."""
    got = answer.get("labels") if isinstance(answer, dict) else None
    got = got if isinstance(got, dict) else {}
    return {c.id: box_label(got.get(c.id)) or c.kind for c in graph.components}


def context_from(answer: dict | None, path_exists: Callable[[str], bool], notes: list[str]) -> ContextDraft:
    d = answer if isinstance(answer, dict) else {}
    where = []
    for w in (d.get("where") or [])[:MAX_WHERE]:
        if not isinstance(w, dict):
            continue
        paths = [p.strip("`/ ") for p in (w.get("paths") or []) if isinstance(p, str)]
        good = [p for p in paths if path_exists(p)]
        if paths and not good:
            notes.append(f"AI_CONTEXT 'where' entry dropped (path not in repo): {plain(w.get('topic'), 40)}")
            continue
        if good:
            where.append((plain(w.get("topic"), 60), good[:4]))
    talk = [plain(x, 200) for x in (d.get("how_they_talk") or []) if isinstance(x, str)][:MAX_TALK]
    return ContextDraft(plain(d.get("overview"), 900), talk, where)


def decision_from(answer: dict | None, c: DecisionCandidate, number: str) -> tuple[DecisionRecord | None, str | None]:
    """→ (record, None) or (None, reason it was not written)."""
    if not isinstance(answer, dict) or not str(answer.get("title") or "").strip():
        return None, f"decision record for {c.key} not written (bad model answer)"
    body = {k: plain(answer.get(k), 900) for k in ("context", "decision", "consequences")}
    title = plain(answer.get("title"), 90).rstrip(".")
    if any(looks_secret(v) for v in (*body.values(), title)):
        return None, f"decision record for {c.key} dropped: secret-looking text"
    conf = answer.get("confidence") if answer.get("confidence") in CONFIDENCE_LEVELS else "low"
    return DecisionRecord(number, title, slug(title), c.type, conf, body["context"], body["decision"],
                          body["consequences"], c), None
