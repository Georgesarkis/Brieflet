"""Rules for text that came from a model before it goes into a doc: flatten, shorten, refuse secrets."""
from __future__ import annotations

import re

SECRET_RE = re.compile(r"(passw|passphrase|api[_-]?key\s*[:=]|token\s*[:=]|secret\s*[:=]|BEGIN [A-Z ]*PRIVATE|"
                       r"sk-ant-|sk-[A-Za-z0-9]{16}|ghp_[A-Za-z0-9]{10})", re.I)


def looks_secret(text: str) -> bool:
    return bool(SECRET_RE.search(text or ""))


def plain(value, max_chars: int) -> str:
    """One line of plain text: no headings, no code fences, single spaces."""
    s = " ".join(l.lstrip("#").strip() for l in str(value or "").splitlines() if not l.strip().startswith("```"))
    return " ".join(s.split())[:max_chars]


def slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:50] or "decision"


def box_label(value) -> str:
    """A diagram label: max 5 words, 40 chars, nothing that breaks Mermaid."""
    s = re.sub(r'["<>\[\]{}()|`#]', "", str(value or "")).strip()
    return " ".join(s.split()[:5])[:40]
