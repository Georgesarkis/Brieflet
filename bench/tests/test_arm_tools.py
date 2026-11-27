"""Arms that bring a tool (e.g. CodeGraph): prepare/cleanup commands + the tool's own setup files. Offline."""
import json

import pytest
import yaml

from bench.infrastructure.config_loader import load
from bench.infrastructure.results_store import JsonlResults
from bench.infrastructure.workspaces import ArmWorkspaces, SetupError


@pytest.fixture
def cfg(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.cs").write_text("class A {}\n")
    tool = tmp_path / "art" / "demo" / "tool"
    (tool / ".claude").mkdir(parents=True)
    (tool / ".mcp.json").write_text(json.dumps({"mcpServers": {"codegraph": {"command": "codegraph", "args": ["serve", "--mcp"]}}}))
    (tool / ".claude" / "CLAUDE.md").write_text("use the tool\n")
    (tmp_path / "q.yaml").write_text(yaml.safe_dump({"questions": [{"id": "q1", "text": "where is A?"}]}))
    data = {"results": str(tmp_path / "res"), "artifacts": str(tmp_path / "art"),
            "repos": {"demo": {"path": str(repo), "questions": "q.yaml"}},
            "arms": {"none": {},
                     "tool": {"overlay": ["{artifacts}/{repo}/tool"], "prepare": ["mkdir .index && echo ok > .index/db"],
                              "cleanup": [f"echo {{dir}} >> {tmp_path / 'cleaned.txt'}"]},
                     "broken": {"prepare": ["exit 3"]}},
            "models": [{"name": "fake", "runner": "fake", "model": "fake"}]}
    p = tmp_path / "bench.yaml"
    p.write_text(yaml.safe_dump(data))
    return load(p)


def test_prepare_overlay_and_cleanup(cfg, tmp_path):
    ws = ArmWorkspaces(cfg, JsonlResults(cfg.results_dir), tmp_path / "w", log=lambda *a: None)
    d = ws.arm("demo", "tool")
    assert (d / ".index" / "db").read_text().strip() == "ok"          # prepare ran inside the copy
    assert (d / ".claude" / "CLAUDE.md").exists() and (d / ".mcp.json").exists()   # dotfiles overlaid
    assert ws.arm("demo", "tool") == d                                # made once, prepare not re-run
    assert not (ws.arm("demo", "none") / ".mcp.json").exists()        # other arms get no MCP
    ws.close()
    assert (tmp_path / "cleaned.txt").read_text().strip() == str(d)   # cleanup got {dir}


def test_prepare_failure_stops(cfg, tmp_path):
    ws = ArmWorkspaces(cfg, JsonlResults(cfg.results_dir), tmp_path / "w", log=lambda *a: None)
    with pytest.raises(SetupError, match="prepare failed"):
        ws.arm("demo", "broken")

