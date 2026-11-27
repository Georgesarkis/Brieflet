"""Folder port on the local disk. Paths are always resolved inside the root; anything outside counts as missing."""
from __future__ import annotations

from pathlib import Path


class DiskFolder:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _inside(self, rel: str) -> Path | None:
        p = (self.root / rel).resolve()
        return p if p == self.root or self.root in p.parents else None

    def exists(self, rel: str) -> bool:
        p = self._inside(rel)
        return bool(p and p.exists())

    def read(self, rel: str) -> str | None:
        p = self._inside(rel)
        return p.read_text(encoding="utf-8") if p and p.is_file() else None

    def write(self, rel: str, text: str) -> None:
        p = self._inside(rel)
        if p is None:
            raise ValueError(f"path outside {self.root}: {rel}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
