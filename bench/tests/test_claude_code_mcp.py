"""claude_code runner: loads only the arm's own MCP servers (.mcp.json) and allows their tools. Offline."""
import json

from bench.infrastructure.runners.claude_code import arm_mcp


def test_claude_code_loads_only_the_arms_mcp(tmp_path):
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"codegraph": {"command": "codegraph"}}}))
    f, tools = arm_mcp(tmp_path)
    assert f.endswith(".mcp.json") and tools == ["mcp__codegraph__*"]
    assert arm_mcp(tmp_path / "missing") == (None, [])
