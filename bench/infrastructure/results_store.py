"""ResultsStore as JSON lines in the results folder: runs.jsonl, learn.jsonl, judge.jsonl, learned/<…>/foldN.md."""
from __future__ import annotations

import json
from pathlib import Path


def _read_jsonl(f: Path) -> list[dict]:
    if not f.exists():
        return []
    with open(f, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _append(f: Path, row: dict) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


class JsonlResults:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    @property
    def runs_path(self) -> Path:
        return self.folder / "runs.jsonl"

    @property
    def learned_dir(self) -> Path:
        return self.folder / "learned"

    def runs(self) -> list[dict]:
        return _read_jsonl(self.runs_path)

    def add_run(self, row: dict) -> None:
        _append(self.runs_path, row)

    def add_learn(self, row: dict) -> None:
        _append(self.folder / "learn.jsonl", row)

    def verdicts(self) -> dict[str, dict]:
        """Latest verdict per row key (a retried judge row overrides the failed one)."""
        return {v["key"]: v for v in _read_jsonl(self.folder / "judge.jsonl")}

    def add_verdict(self, rec: dict) -> None:
        _append(self.folder / "judge.jsonl", rec)

    def learned_file(self, repo: str, model: str, arm: str, fold: int) -> Path:
        return self.learned_dir / repo / model / arm / f"fold{fold + 1}.md"

    def save_learned(self, repo: str, model: str, arm: str, fold: int, text: str) -> Path:
        f = self.learned_file(repo, model, arm, fold)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        return f
