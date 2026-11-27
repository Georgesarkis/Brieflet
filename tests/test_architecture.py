"""Architecture rules as tests (like NetArchTest in .NET): dependencies only point inward.

    presentation ─┐
                  ├─> application ──> domain
    infrastructure┘
Domain imports nothing from the other layers (and no IO libraries). Application imports only domain.
Infrastructure and presentation never import each other; the composition roots
(brieflet/bootstrap.py, bench/bootstrap.py) are the only places that wire concrete classes together.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("domain", "application", "infrastructure", "presentation")
ALLOWED = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "infrastructure": {"domain", "application", "infrastructure"},
    "presentation": {"domain", "application", "presentation"},
}
IO_LIBS = {"subprocess", "requests", "anthropic", "openai", "yaml", "shutil", "tempfile"}


def layer_of(path: Path) -> str | None:
    parts = path.relative_to(ROOT).parts
    return parts[1] if len(parts) > 2 and parts[1] in LAYERS else None


def imported_modules(path: Path) -> set[str]:
    """Absolute module names this file imports (relative imports resolved)."""
    pkg = list(path.relative_to(ROOT).with_suffix("").parts[:-1])
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = pkg[: len(pkg) - node.level + 1] if node.level else []
            mod = ".".join(base + ([node.module] if node.module else []))
            out.add(mod)
            out |= {f"{mod}.{a.name}" for a in node.names}
    return out


def files():
    return [p for app in ("brieflet", "bench") for p in (ROOT / app).rglob("*.py")
            if layer_of(p) and "tests" not in p.parts]


@pytest.mark.parametrize("path", files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_dependencies_point_inward(path):
    app, layer = path.relative_to(ROOT).parts[0], layer_of(path)
    rel = str(path.relative_to(ROOT))
    allowed = ALLOWED[layer]
    for mod in imported_modules(path):
        parts = mod.split(".")
        if parts[0] == app and len(parts) > 1 and parts[1] in LAYERS:
            assert parts[1] in allowed, f"{rel} ({layer}) imports {mod}"
        if layer == "domain":
            assert parts[0] not in IO_LIBS, f"{rel}: domain must stay pure, imports {mod}"
