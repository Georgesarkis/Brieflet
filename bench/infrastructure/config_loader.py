"""bench.yaml (+ prices, the question files and their .refs.yaml) → BenchConfig.

Prices (USD per 1M tokens, one section per runner) merge in this order, later wins: bench/prices.yaml,
plugin packages (`brieflet.bench_prices` entry points, each a dict), the bench.yaml `prices:` block.
"""
from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

import yaml

from ..application.config import BenchConfig

BENCH_DIR = Path(__file__).resolve().parents[1]


def _yaml(path: Path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _prices(data: dict) -> dict:
    out: dict = {}
    for layer in [_yaml(BENCH_DIR / "prices.yaml")] + [ep.load() for ep in entry_points(group="brieflet.bench_prices")] \
            + [data.get("prices")]:
        for runner, table in (layer or {}).items():
            out.setdefault(runner, {}).update(table or {})
    return out


def load(path: str | Path) -> BenchConfig:
    data = _yaml(Path(path))
    cfg = BenchConfig(data, Path(path).resolve().parent, _prices(data))
    for repo, rc in cfg.repos.items():
        qfile = cfg.path(rc["questions"])
        cfg.questions[repo] = _yaml(qfile)["questions"]
        refs = qfile.with_name(qfile.stem + ".refs.yaml")
        cfg.refs[repo] = (_yaml(refs) or {}) if refs.exists() else {}
    return cfg
