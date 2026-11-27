"""RepoSnapshot over git: reads files at one commit (no checkout, no build)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..application.ports import RepoUnreadable


class GitError(RepoUnreadable):
    pass


class GitSnapshot:
    def __init__(self, repo: Path, rev: str = "HEAD"):
        self.repo, self.rev = Path(repo), rev
        self.files = self._git("ls-tree", "-r", "--name-only", rev).splitlines()
        self._set = set(self.files)
        self._cache: dict[str, str | None] = {}

    def _git(self, *args: str) -> str:
        r = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise GitError(f"git {args[0]}: {r.stderr.strip()[-200:]}")
        return r.stdout

    def has(self, path: str) -> bool:
        return path in self._set

    def has_dir(self, path: str) -> bool:
        d = path.rstrip("/") + "/"
        return any(f.startswith(d) for f in self.files)

    def read(self, path: str) -> str | None:
        if path not in self._cache:
            self._cache[path] = self._show(path) if path in self._set else None
        return self._cache[path]

    def _show(self, path: str) -> str | None:
        r = subprocess.run(["git", "-C", str(self.repo), "show", f"{self.rev}:{path}"], capture_output=True, timeout=60)
        return r.stdout.decode("utf-8", "replace").lstrip("﻿") if r.returncode == 0 else None

    def commit_that_added(self, path: str) -> str | None:
        """'<sha> <date> <subject>' of the oldest commit that added the file; None without history."""
        r = subprocess.run(["git", "-C", str(self.repo), "log", "--diff-filter=A", "--format=%H %as %s", "--", path],
                           capture_output=True, text=True, timeout=120)
        lines = r.stdout.strip().splitlines() if r.returncode == 0 else []
        return lines[-1] if lines else None
