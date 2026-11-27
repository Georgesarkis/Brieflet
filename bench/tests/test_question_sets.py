"""Shipped question sets and configs stay consistent: every question has reference points for the judge."""
from pathlib import Path

import pytest
import yaml

from bench.infrastructure.config_loader import load

BENCH = Path(__file__).resolve().parents[1]
TYPES = {"overview", "trace", "change", "detail"}
CONFIGS = ["pilot.yaml", "eshoponweb.yaml", "calcom.yaml"]


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


def test_calcom_is_one_night_with_learning():
    cfg = load(BENCH / "calcom.yaml")
    runs = sum(len(qs) for *_, qs in cfg.matrix(None)) * cfg.repeats
    assert runs == 40                           # ROADMAP Day 5: 4 setups × 10 q × 1, max 40 per night
    assert set(cfg.arms) == {"none", "brieflet", "codegraph", "brieflet-learn"}
    assert cfg.is_learn("brieflet-learn") and not cfg.is_learn("brieflet")
    repo = "calcom-ae027bb"
    types = [q["type"] for q in cfg.questions[repo]]
    assert {t: types.count(t) for t in TYPES} == {"overview": 3, "trace": 3, "change": 2, "detail": 2}
    assert cfg.folds(repo) == [["q1", "q2", "q3", "q4", "q5"], ["q6", "q7", "q8", "q9", "q10"]]
    strip = set(cfg.repos[repo]["strip"])
    assert {"CLAUDE.md", "AGENTS.md", "agents", ".claude", ".cursor"} <= strip   # cal.com ships its own AI docs


@pytest.mark.parametrize("repo", ["eshoponweb-4da8212", "calcom-ae027bb"])
def test_codegraph_overlay_is_shipped(repo):
    art = BENCH / "artifacts" / repo / "codegraph"
    for f in [".mcp.json", ".claude/settings.json", ".claude/CLAUDE.md"]:
        assert (art / f).is_file(), f
