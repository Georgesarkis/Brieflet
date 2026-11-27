"""bench.yaml (+ bench/prices.yaml, the question files and their .refs.yaml) → BenchConfig."""
from __future__ import annotations

from pathlib import Path

import yaml

from ..application.config import BenchConfig

BENCH_DIR = Path(__file__).resolve().parents[1]


def _yaml(path: Path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load(path: str | Path) -> BenchConfig:
    cfg = BenchConfig(_yaml(Path(path)), Path(path).resolve().parent, _yaml(BENCH_DIR / "prices.yaml"))
    for repo, rc in cfg.repos.items():
        qfile = cfg.path(rc["questions"])
        cfg.questions[repo] = _yaml(qfile)["questions"]
        refs = qfile.with_name(qfile.stem + ".refs.yaml")
        cfg.refs[repo] = (_yaml(refs) or {}) if refs.exists() else {}
    return cfg
