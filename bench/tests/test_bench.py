"""Offline tests: no network, no keys, no cost.  python -m pytest bench/tests"""
import json
from pathlib import Path

import pytest
import yaml

from bench.application.plan_benchmark import PlanBenchmark
from bench.infrastructure.config_loader import load
from bench.infrastructure.results_store import JsonlResults
from bench.infrastructure.runners import fake
from bench.infrastructure.workspaces import ArmWorkspaces
from bench.presentation.cli import main


def must_not_run(name):
    pytest.fail("must not call a paid runner")


@pytest.fixture
def setup(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "Basket.cs").write_text("class Basket {}\n// AddGrpcClient basket-api\n")
    (repo / "CLAUDE.md").write_text("old docs, must be stripped")
    art = tmp_path / "art" / "demo" / "brieflet"
    art.mkdir(parents=True)
    (art / "AI_CONTEXT.md").write_text("# context\nBasket lives in src/Basket.cs\n")
    (art / "CLAUDE.md").write_text("Read AI_CONTEXT.md first.\n")
    (tmp_path / "q.yaml").write_text(yaml.safe_dump({"questions": [{"id": "q1", "type": "trace", "text": "where is the basket?"}]}))
    cfg = {"repeats": 2, "max_usd": 1, "results": str(tmp_path / "res"), "artifacts": str(tmp_path / "art"),
           "repos": {"demo": {"path": str(repo), "questions": "q.yaml", "strip": ["CLAUDE.md"]}},
           "arms": {"none": {}, "brieflet": {"overlay": ["{artifacts}/{repo}/brieflet"]}},
           "models": [{"name": "fake", "runner": "fake", "model": "fake"}]}
    p = tmp_path / "bench.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p, tmp_path


def test_fake_run_and_report(setup, capsys):
    p, tmp = setup
    assert main(["run", "-c", str(p)]) == 0
    rows = [json.loads(l) for l in open(tmp / "res" / "runs.jsonl")]
    assert len(rows) == 4 and {r["arm"] for r in rows} == {"none", "brieflet"}
    assert main(["report", "-c", str(p)]) == 0
    assert "| demo | fake | brieflet |" in capsys.readouterr().out


def test_arms_strip_and_overlay(setup, tmp_path):
    p, _ = setup
    cfg = load(p)
    ws = ArmWorkspaces(cfg, JsonlResults(cfg.results_dir), tmp_path / "w")
    none = ws.arm("demo", "none")
    assert not (none / "CLAUDE.md").exists() and (none / "src" / "Basket.cs").exists()
    br = ws.arm("demo", "brieflet")
    assert (br / "CLAUDE.md").read_text().startswith("Read AI_CONTEXT")



def test_arm_copy_skips_dangling_symlinks_and_strips_folders(setup, tmp_path):
    p, t = setup
    repo = t / "repo"
    (repo / "pkg").mkdir()
    (repo / "pkg" / ".env").symlink_to("../../missing.env")      # like cal.com packages/prisma/.env
    (repo / "agents").mkdir()
    (repo / "agents" / "rules.md").write_text("their own AI docs")
    (repo / "AGENTS.md").write_text("their own AI docs")
    (repo / "CLAUDE.md").unlink()
    (repo / "CLAUDE.md").symlink_to("AGENTS.md")
    cfg = yaml.safe_load(open(p))
    cfg["repos"]["demo"]["strip"] = ["CLAUDE.md", "AGENTS.md", "agents"]
    p.write_text(yaml.safe_dump(cfg))
    c = load(p)
    none = ArmWorkspaces(c, JsonlResults(c.results_dir), tmp_path / "w").arm("demo", "none")
    assert (none / "src" / "Basket.cs").exists()
    assert not (none / "pkg" / ".env").exists()
    assert not any((none / x).exists() for x in ["CLAUDE.md", "AGENTS.md", "agents"])


def test_own_docs_arm_keeps_repo_docs(setup, tmp_path):
    p, _ = setup
    cfg = yaml.safe_load(open(p))
    cfg["arms"]["own-docs"] = {"keep_repo_docs": True}
    p.write_text(yaml.safe_dump(cfg))
    c = load(p)
    ws = ArmWorkspaces(c, JsonlResults(c.results_dir), tmp_path / "w")
    assert (ws.arm("demo", "own-docs") / "CLAUDE.md").read_text() == "old docs, must be stripped"
    assert not (ws.arm("demo", "none") / "CLAUDE.md").exists()

def _paid(p, **extra):
    cfg = yaml.safe_load(open(p))
    cfg["models"] = [{"name": "paid", "runner": "paid-plugin", "model": "big"}]
    cfg["prices"] = {"paid-plugin": {"big": {"input": 2.0, "output": 10.0}}}
    cfg.update(extra)
    p.write_text(yaml.safe_dump(cfg))


def test_paid_needs_yes(setup):
    p, _ = setup
    _paid(p, max_usd=100)
    assert main(["run", "-c", str(p)], runner_for=must_not_run) == 2


def test_paid_over_budget_refused(setup):
    p, _ = setup
    _paid(p, max_usd=0.01)
    assert main(["run", "-c", str(p), "--yes"], runner_for=must_not_run) == 2


def test_unpriced_plugin_refused(setup):
    p, _ = setup
    cfg = yaml.safe_load(open(p))
    cfg["models"] = [{"name": "unpriced", "runner": "paid-plugin", "model": "no-price"}]
    cfg["max_usd"] = 1000
    p.write_text(yaml.safe_dump(cfg))
    assert main(["run", "-c", str(p), "--yes"], runner_for=must_not_run) == 2


def test_subscription_is_free(setup):
    p, _ = setup
    cfg = load(p)
    cfg.data["models"] = [{"name": "sub", "runner": "plan-plugin", "model": "m", "billing": "subscription"}]
    t = PlanBenchmark(cfg, JsonlResults(cfg.results_dir)).execute().totals
    assert t.paid_runs == 0 and t.sub_runs == 4


def test_judge_free_and_report(setup, capsys):
    p, tmp = setup
    (tmp / "q.refs.yaml").write_text(yaml.safe_dump({"q1": {"must": ["basket in Basket.cs", "uses gRPC"]}}))
    assert main(["run", "-c", str(p)]) == 0
    assert main(["judge", "-c", str(p)], judge=None) == 2          # no judge: block → refused, nothing called
    cfg = yaml.safe_load(open(p)); cfg["judge"] = {"runner": "judge-plugin", "model": "m", "billing": "subscription"}
    p.write_text(yaml.safe_dump(cfg))
    calls = []
    class FakeJudge:
        def ask(self, jc, text):
            calls.append(text)
            return json.dumps({"must": [True, len(calls) % 2 == 0], "wrong_claims": []}), {"cost_usd": 0}
    assert main(["judge", "-c", str(p)], judge=FakeJudge()) == 0 and len(calls) == 4
    assert main(["judge", "-c", str(p)], judge=FakeJudge()) == 0 and len(calls) == 4  # already judged: nothing new
    capsys.readouterr()
    main(["report", "-c", str(p)])
    out = capsys.readouterr().out
    assert "3.00 (n=2)" in out and "1.00 (n=2)" in out and "| 5,000 |" in out


def test_judge_score_rule():
    from bench.domain.scoring import score
    assert score(2, {"must": [True, True], "wrong_claims": []}) == 3
    assert score(3, {"must": [True, True, False], "wrong_claims": []}) == 2
    assert score(3, {"must": [True, False, False], "wrong_claims": []}) == 1
    assert score(2, {"must": [True, True], "wrong_claims": [{"severity": "major"}]}) == 0
    assert score(2, {"must": [True, True], "wrong_claims": [{"severity": "minor"}]}) == 2


def test_stop_on_errors_then_resume(setup):
    p, tmp = setup
    cfg = yaml.safe_load(open(p)); cfg["repeats"] = 3; p.write_text(yaml.safe_dump(cfg))
    real = fake.run
    state = {"n": 0}
    def flaky(*a, **k):
        state["n"] += 1
        r = real(*a, **k)
        if state["n"] > 2:
            r["error"] = "usage limit"
        return r
    assert main(["run", "-c", str(p)], runner_for=lambda name: flaky) == 4          # stops after 3 errors in a row
    assert state["n"] == 5
    assert main(["run", "-c", str(p), "--resume"], runner_for=lambda name: real) == 0
    ok = [json.loads(l) for l in open(tmp / "res" / "runs.jsonl") if not json.loads(l).get("error")]
    assert len(ok) == 6 and len({(r["arm"], r["rep"]) for r in ok}) == 6


def test_learn_folds_never_leak(setup):
    """Learn on fold 1, measured on fold 2 with ONLY fold 1's facts (and the other way round)."""
    p, tmp = setup
    cfg = yaml.safe_load(p.read_text())
    (tmp / "q.yaml").write_text(yaml.safe_dump({"questions": [
        {"id": f"q{i}", "type": "trace", "text": f"question {i}"} for i in (1, 2, 3, 4)]}))
    cfg["arms"]["learn"] = {"overlay": ["{artifacts}/{repo}/brieflet"], "learn": True}
    p.write_text(yaml.safe_dump(cfg))
    seen = {}

    def fake_run(question, wd, m, price, cap):
        lm = Path(wd, "LEARNED.md")
        seen.setdefault(question.split("\n")[0], []).append(lm.read_text() if lm.exists() else "")
        n = question.split()[1]
        return {"input_tokens": 0, "cache_read": 10, "cache_write": 0, "output_tokens": 1, "turns": 1, "secs": 0.0,
                "cost_usd": 0.0, "error": None,
                "answer": f"answer\nLEARNED:\n- fact from q{n} → `src/Basket.cs`\n- bogus q{n} → `nope/gone.cs`"}
    assert main(["run", "-c", str(p)], runner_for=lambda r: fake_run) == 2   # learn arm without a learning pass: refused
    assert main(["learn", "-c", str(p)], runner_for=lambda r: fake_run) == 0
    f1 = (tmp / "res" / "learned" / "demo" / "fake" / "learn" / "fold1.md").read_text()
    assert "fact from q1" in f1 and "fact from q2" in f1 and "q3" not in f1 and "bogus" not in f1
    seen.clear()
    assert main(["run", "-c", str(p)], runner_for=lambda r: fake_run) == 0
    q3 = next(t for t in seen["question 3"] if t)          # measured run of q3 (fold 2): sees fold 1 facts only
    assert sum(1 for t in seen["question 3"] if t) == 2  # only the learn arm (2 repeats) has LEARNED.md
    assert "fact from q1" in q3 and "fact from q3" not in q3
    q1 = next(t for t in seen["question 1"] if t)
    assert "fact from q3" in q1 and "fact from q1" not in q1


def test_learned_md_prune(tmp_path):
    """Duplicates, secrets, missing paths and paths outside the repo never reach LEARNED.md."""
    from brieflet.domain.learned import parse_facts
    (tmp_path / "a.cs").write_text("x")
    ws = ArmWorkspaces(None, None, tmp_path / "w")
    ws.add_learned(tmp_path, "LEARNED:\n- A is here → `a.cs`\n- A is here → `a.cs`\n- api_key: abc → `a.cs`")
    ws.add_learned(tmp_path, "LEARNED:\n- gone → `b.cs`\n- escape → `../etc/passwd`")
    assert [f.fact for f in parse_facts((tmp_path / "LEARNED.md").read_text())] == ["A is here"]


def test_only_local_runners_built_in():
    from bench.infrastructure import runners
    assert set(runners.MODULES) == {"fake"}
    with pytest.raises(ValueError):
        runners.runner_for("no-such-runner")
