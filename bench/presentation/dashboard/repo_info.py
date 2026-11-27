"""What a tested repo is: full name, open or closed source, size and main language. Shown on the repo buttons.

Measured from the checkout when it is on this machine (files + lines of code, language by lines);
otherwise taken from the artifacts' meta.yaml (`source`, `license`, `language`, `files`, `loc`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LANG = {".cs": "C#", ".razor": "C#", ".cshtml": "C#", ".fs": "F#", ".vb": "VB.NET", ".py": "Python", ".ts": "TypeScript",
        ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".go": "Go", ".rs": "Rust",
        ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".c": "C", ".h": "C",
        ".cpp": "C++", ".cc": "C++", ".hpp": "C++", ".scala": "Scala", ".dart": "Dart", ".ex": "Elixir", ".vue": "Vue",
        ".svelte": "Svelte"}
SKIP = {".git", "node_modules", "bin", "obj", "dist", "build", "vendor", ".venv", "venv", "__pycache__", "wwwroot",
        ".codegraph", "target", ".next"}


@dataclass
class RepoInfo:
    key: str                  # config name, e.g. eshoponweb-4da8212
    name: str                 # full name, e.g. dotnet-architecture/eShopOnWeb
    sha: str = ""
    open_source: bool = True
    license: str = ""
    language: str = ""
    files: int | None = None  # source files in known languages
    loc: int | None = None    # non-empty lines in those files

    @property
    def size(self) -> str:
        if self.loc is None:
            return ""
        lines = f"{self.loc / 1000:,.0f}k lines" if self.loc >= 1000 else f"{self.loc} lines"
        return f"{self.files:,} files · {lines}" if self.files is not None else lines


def measure(root: Path) -> tuple[str, int, int] | None:
    """(main language, source files, non-empty lines) of a checkout, or None if it isn't here."""
    if not root.is_dir():
        return None
    by_lang: dict[str, int] = {}
    files = 0
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for n in names:
            lang = LANG.get(os.path.splitext(n)[1].lower())
            if not lang:
                continue
            try:
                with open(os.path.join(d, n), encoding="utf-8", errors="replace") as fh:
                    lines = sum(1 for l in fh if l.strip())
            except OSError:
                continue
            files += 1
            by_lang[lang] = by_lang.get(lang, 0) + lines
    if not by_lang:
        return None
    return max(by_lang, key=by_lang.get), files, sum(by_lang.values())


def info(key: str, repo_cfg: dict, meta: dict, root: Path | None) -> RepoInfo:
    src = str(meta.get("source", "open")).lower()
    r = RepoInfo(key=key, name=str(meta.get("repo") or key), sha=str(repo_cfg.get("sha") or meta.get("sha") or "")[:7],
                 open_source=src != "closed", license=str(meta.get("license") or ""),
                 language=str(meta.get("language") or ""), files=meta.get("files"), loc=meta.get("loc"))
    m = measure(root) if root else None
    if m:
        r.language, r.files, r.loc = m
    return r
