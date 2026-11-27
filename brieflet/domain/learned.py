"""LEARNED.md facts: what an assistant had to dig out of the code because AI_CONTEXT.md didn't have it.

Line format (the contract assistants write to):  - <fact> → `path/in/repo`   (optional suffix, e.g. · 2026-11-26)
Rules that keep the log from rotting: every fact points at a path that exists, no secrets, no duplicates,
at most MAX_FACTS (oldest dropped first).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .model_text import looks_secret

FILE = "LEARNED.md"
MAX_FACTS = 60
MAX_PER_ANSWER = 3
LINE_RE = re.compile(r"^\s*[-*]\s+(?P<fact>.+?)\s*(?:→|->)\s*`(?P<path>[^`]+)`(?P<rest>.*)$")
ANSWER_MARK = "LEARNED:"


@dataclass(frozen=True)
class LearnedFact:
    fact: str
    path: str
    rest: str = ""                 # anything after the path, e.g. "· 2026-11-26"

    def dedupe_key(self) -> tuple[str, str]:
        return self.path.lower(), re.sub(r"\W+", " ", self.fact.lower()).strip()


def parse_facts(text: str) -> list[LearnedFact]:
    out = []
    for line in (text or "").splitlines():
        if m := LINE_RE.match(line):
            out.append(LearnedFact(" ".join(m.group("fact").split())[:220], m.group("path").strip().strip("/"),
                                   m.group("rest").strip()))
    return out


def facts_from_answer(answer: str) -> list[LearnedFact]:
    """The 'LEARNED:' block at the end of an assistant's answer."""
    i = (answer or "").rfind(ANSWER_MARK)
    if i < 0:
        return []
    return parse_facts(answer[i + len(ANSWER_MARK):])[:MAX_PER_ANSWER]


def prune(facts: list[LearnedFact], path_exists: Callable[[str], bool]) -> tuple[list[LearnedFact], list[str]]:
    """Valid, unique, newest MAX_FACTS facts + one reason per dropped fact."""
    keep, seen, dropped = [], set(), []
    for f in facts:
        if f.dedupe_key() in seen:
            continue
        if looks_secret(f.fact):
            dropped.append(f"secret-looking: {f.fact[:40]}")
            continue
        if not path_exists(f.path):
            dropped.append(f"path gone: {f.path}")
            continue
        seen.add(f.dedupe_key())
        keep.append(f)
    if len(keep) > MAX_FACTS:
        dropped += [f"over {MAX_FACTS} lines: {f.fact[:40]}" for f in keep[:-MAX_FACTS]]
        keep = keep[-MAX_FACTS:]
    return keep, dropped
