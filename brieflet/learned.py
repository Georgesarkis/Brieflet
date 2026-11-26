"""LEARNED.md: facts an assistant had to dig out of the code because AI_CONTEXT.md didn't have them.

One fact per line:  - <fact> → `path/in/repo`   (optional date suffix: · 2026-11-26)
Rules that keep it from rotting: every line must point at a path that exists, no secrets, no duplicates,
at most MAX_LINES (oldest dropped first). `brieflet init` re-checks the file every run.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

FILE = "LEARNED.md"
MAX_LINES = 60
MAX_PER_ANSWER = 3
LINE_RE = re.compile(r"^\s*[-*]\s+(?P<fact>.+?)\s*(?:→|->)\s*`(?P<path>[^`]+)`(?P<rest>.*)$")
SECRET_RE = re.compile(r"(passw|passphrase|api[_-]?key\s*[:=]|token\s*[:=]|secret\s*[:=]|BEGIN [A-Z ]*PRIVATE|sk-[A-Za-z0-9]{16})", re.I)

HEADER = """# Learned

Facts an AI assistant had to find in the code because [AI_CONTEXT.md](AI_CONTEXT.md) didn't have them.
One line each: fact → `path`. Brieflet drops lines whose path no longer exists.

"""

RULE = """
**When the docs were not enough:** if you had to search the code to answer, add ONE line per missing fact to
[LEARNED.md](LEARNED.md): `- <fact, max 25 words> → \\`path/to/file\\``. Check LEARNED.md before searching the code.
"""

PROMPT_SUFFIX = ("\n\n(After your answer: if the project docs did not already contain what you needed and you had to search "
                 "the code, end with a block that starts with the line LEARNED: followed by up to 3 lines in the form "
                 "'- <fact, max 25 words> → `path/to/file`'. If the docs were enough, end with the line LEARNED: none)")


def parse_lines(text: str) -> list[dict]:
    out = []
    for l in (text or "").splitlines():
        if m := LINE_RE.match(l):
            out.append({"fact": " ".join(m.group("fact").split())[:220], "path": m.group("path").strip().strip("/"),
                        "rest": m.group("rest").strip()})
    return out


def from_answer(answer: str) -> list[dict]:
    """The LEARNED: block at the end of an answer (benchmark learning pass)."""
    i = (answer or "").rfind("LEARNED:")
    if i < 0:
        return []
    return parse_lines(answer[i + len("LEARNED:"):])[:MAX_PER_ANSWER]


def exists(root: Path, rel: str) -> bool:
    rel = rel.split(":")[0].split("#")[0]
    p = (Path(root) / rel).resolve()
    return (p == Path(root).resolve() or Path(root).resolve() in p.parents) and p.exists()


def clean(entries: list[dict], root: Path) -> tuple[list[dict], list[str]]:
    """Valid, unique, newest MAX_LINES entries + reasons for what was dropped."""
    keep, seen, dropped = [], set(), []
    for e in entries:
        key = (e["path"].lower(), re.sub(r"\W+", " ", e["fact"].lower()).strip())
        if key in seen:
            continue
        if SECRET_RE.search(e["fact"]):
            dropped.append(f"secret-looking: {e['fact'][:40]}")
            continue
        if not exists(root, e["path"]):
            dropped.append(f"path gone: {e['path']}")
            continue
        seen.add(key)
        keep.append(e)
    if len(keep) > MAX_LINES:
        dropped += [f"over {MAX_LINES} lines: {e['fact'][:40]}" for e in keep[:-MAX_LINES]]
        keep = keep[-MAX_LINES:]
    return keep, dropped


def render(entries: list[dict]) -> str:
    rows = [f"- {e['fact']} → `{e['path']}`" + (f" {e['rest']}" if e.get("rest") else "") for e in entries]
    return HEADER + ("\n".join(rows) if rows else "_(nothing yet)_") + "\n"


def add(path: Path, root: Path, new: list[dict]) -> tuple[int, list[str]]:
    """Append new facts to LEARNED.md at `path` (checked against repo `root`). → (lines added, dropped reasons)."""
    old = parse_lines(path.read_text(encoding="utf-8")) if path.exists() else []
    stamp = f"· {date.today().isoformat()}"
    merged, dropped = clean(old + [{**e, "rest": e.get("rest") or stamp} for e in new], root)
    path.write_text(render(merged), encoding="utf-8")
    return len(merged) - len([e for e in old if e in merged]), dropped
