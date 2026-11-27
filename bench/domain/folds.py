"""Fair learning: question ids split in N folds. Learn on one fold, measure on the others, never on itself."""
from __future__ import annotations


def split(ids: list[str], n: int) -> list[list[str]]:
    k = -(-len(ids) // n)
    return [ids[i:i + k] for i in range(0, len(ids), k)]


def fold_of(folds: list[list[str]], qid: str) -> int:
    return next(i for i, f in enumerate(folds) if qid in f)
