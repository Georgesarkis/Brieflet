"""Shipped question sets and configs stay consistent: every question has reference points for the judge."""
from pathlib import Path

import pytest
import yaml

from bench.infrastructure.config_loader import load

BENCH = Path(__file__).resolve().parents[1]
TYPES = {"overview", "trace", "change", "detail"}
CONFIGS = ["pilot.yaml", "eshoponweb.yaml"]


@pytest.mark.parametrize("name", CONFIGS)
def test_config_loads_with_refs_for_every_question(name):
    cfg = load(BENCH / name)
    for repo, qs in cfg.questions.items():
        ids = [q["id"] for q in qs]
        assert len(ids) == len(set(ids)), f"{repo}: duplicate question ids"
        assert {q["type"] for q in qs} <= TYPES
        for qid in ids:
            assert cfg.refs[repo].get(qid, {}).get("must"), f"{repo} {qid}: no `must` reference points"


def test_eshoponweb_is_one_night():
    cfg = load(BENCH / "eshoponweb.yaml")
    runs = sum(len(qs) for *_, qs in cfg.matrix(None)) * cfg.repeats
    assert runs == 30 and runs <= 40            # ROADMAP: max 40 runs per night
    assert set(cfg.arms) == {"none", "brieflet", "codegraph"}
    types = [q["type"] for q in cfg.questions["eshoponweb-4da8212"]]
    assert {t: types.count(t) for t in TYPES} == {"overview": 3, "trace": 3, "change": 2, "detail": 2}


def test_codegraph_overlay_is_shipped():
    art = BENCH / "artifacts" / "eshoponweb-4da8212" / "codegraph"
    for f in [".mcp.json", ".claude/settings.json", ".claude/CLAUDE.md"]:
        assert (art / f).is_file(), f
