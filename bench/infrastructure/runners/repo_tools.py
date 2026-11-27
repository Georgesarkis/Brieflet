"""Read-only repo tools for the API runners (Anthropic + OpenAI get the exact same three tools).

Every path is resolved inside the arm's working copy; anything outside is refused. Output is capped so one
call can't flood the context (the cap is part of the benchmark setup and is logged with every run).
"""
from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

MAX_CHARS = 20_000
MAX_MATCHES = 200
SKIP_DIRS = {".git", "node_modules", "bin", "obj", ".vs", ".idea", "__pycache__"}

SPECS = [
    {
        "name": "list_files",
        "description": "List files in the repository whose path matches a glob (e.g. '**/*.cs', 'src/Basket*/**'). "
                       "Returns repo-relative paths, one per line.",
        "schema": {"type": "object", "additionalProperties": False, "required": ["glob"],
                   "properties": {"glob": {"type": "string", "description": "Glob relative to the repo root."}}},
    },
    {
        "name": "grep",
        "description": "Search file contents with a regular expression. Returns 'path:line: text' rows.",
        "schema": {"type": "object", "additionalProperties": False, "required": ["pattern", "glob"],
                   "properties": {"pattern": {"type": "string", "description": "Python regular expression."},
                                  "glob": {"type": "string", "description": "Only files matching this glob; '**/*' for all."}}},
    },
    {
        "name": "read_file",
        "description": "Read a text file from the repository, with line numbers. Use offset/limit for long files.",
        "schema": {"type": "object", "additionalProperties": False, "required": ["path", "offset", "limit"],
                   "properties": {"path": {"type": "string"},
                                  "offset": {"type": "integer", "description": "First line, 1-based."},
                                  "limit": {"type": "integer", "description": "Max lines to return (≤ 2000)."}}},
    },
]


class RepoTools:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _inside(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"path outside the repository: {rel}")
        return p

    def _files(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for f in sorted(filenames):
                yield Path(dirpath, f).relative_to(self.root).as_posix()

    @staticmethod
    def _match(path: str, glob: str) -> bool:
        glob = glob.lstrip("./") or "**/*"
        return fnmatch.fnmatch(path, glob) or (glob.startswith("**/") and fnmatch.fnmatch(path, glob[3:]))

    def list_files(self, glob: str) -> str:
        hits = [p for p in self._files() if self._match(p, glob)]
        out = "\n".join(hits[:MAX_MATCHES])
        if len(hits) > MAX_MATCHES:
            out += f"\n… {len(hits) - MAX_MATCHES} more, narrow the glob"
        return out or "no files match"

    def grep(self, pattern: str, glob: str) -> str:
        rx = re.compile(pattern)
        rows = []
        for p in self._files():
            if not self._match(p, glob):
                continue
            try:
                with open(self.root / p, encoding="utf-8", errors="strict") as fh:
                    for n, line in enumerate(fh, 1):
                        if rx.search(line):
                            rows.append(f"{p}:{n}: {line.rstrip()[:300]}")
                            if len(rows) >= MAX_MATCHES:
                                return "\n".join(rows) + "\n… more matches, narrow the pattern or glob"
            except (UnicodeDecodeError, OSError):
                continue
        return "\n".join(rows) or "no matches"

    def read_file(self, path: str, offset: int = 1, limit: int = 400) -> str:
        p = self._inside(path)
        if not p.is_file():
            return f"not a file: {path}"
        offset, limit = max(1, int(offset)), max(1, min(int(limit), 2000))
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        chunk = lines[offset - 1: offset - 1 + limit]
        out = "\n".join(f"{offset + i}\t{l}" for i, l in enumerate(chunk))
        if offset - 1 + limit < len(lines):
            out += f"\n… file has {len(lines)} lines"
        return out

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        """Returns (text, is_error). Output capped at MAX_CHARS."""
        try:
            fn = {"list_files": self.list_files, "grep": self.grep, "read_file": self.read_file}[name]
            text = fn(**args)
            err = False
        except KeyError:
            text, err = f"unknown tool {name}", True
        except (TypeError, ValueError, re.error, OSError) as e:
            text, err = f"error: {e}", True
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + f"\n… cut at {MAX_CHARS} chars"
        return text, err
