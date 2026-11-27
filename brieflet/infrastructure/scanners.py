"""Scanner chains: the first component scanner that finds something wins; decision scanners all add candidates."""
from __future__ import annotations

from ..domain.components import ComponentGraph
from ..domain.decisions import DecisionCandidate


class FirstFound:
    """ComponentScanner: try each scanner in order (e.g. .NET Aspire first, then the any-language one)."""

    def __init__(self, *scanners):
        self.scanners = scanners

    def scan(self, snapshot) -> ComponentGraph:
        graph = ComponentGraph(None)
        for s in self.scanners:
            graph = s.scan(snapshot)
            if not graph.is_empty:
                return graph
        return graph


class AllDecisions:
    """DecisionScanner: every scanner's candidates, first one wins when two find the same decision key."""

    def __init__(self, *scanners):
        self.scanners = scanners

    def scan(self, snapshot, graph: ComponentGraph) -> list[DecisionCandidate]:
        out: dict[str, DecisionCandidate] = {}
        for s in self.scanners:
            for c in s.scan(snapshot, graph):
                out.setdefault(c.key, c)
        return list(out.values())
