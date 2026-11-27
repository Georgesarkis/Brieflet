"""Component graph: the boxes (deployable parts, libraries, infrastructure) and arrows of a system. Pure data, no IO."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

STORAGE_KINDS = ("cache", "queue", "database")
MAX_BOXES = 15


@dataclass
class Component:
    id: str
    name: str
    kind: str                      # service | library | module | group | cache | queue | database | proxy | container | auth
    shape: str                     # box | db | queue | hex (diagram shape)
    path: str | None = None        # repo folder of a project; None for infrastructure
    tech: str | None = None        # e.g. "Redis" for infrastructure
    packages: list[str] = field(default_factory=list)
    databases: dict[str, str] = field(default_factory=dict)  # code variable → database name
    entry: str | None = None       # entry point file (main.py, src/main.rs, …) when one is known

    @property
    def is_storage(self) -> bool:
        return self.kind in STORAGE_KINDS


@dataclass
class Link:
    source: str
    target: str
    label: str = ""
    dotted: bool = False           # dotted = gets a URL (auth), solid = calls / uses


@dataclass
class ComponentGraph:
    apphost: str | None            # .NET Aspire AppHost folder; None for other repos
    components: list[Component] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    project_refs: dict[str, list[str]] = field(default_factory=dict)  # component id → referenced projects
    origin: str = ""               # what the graph was read from, for the docs ("`src/AppHost`, the project files …")
    notes: list[str] = field(default_factory=list)   # what the scanner skipped or cut, shown in the init output

    @property
    def is_empty(self) -> bool:
        return not self.components

    def name_of(self, cid: str) -> str:
        return next(c.name for c in self.components if c.id == cid)

    def outgoing(self, cid: str) -> list[Link]:
        return [l for l in self.links if l.source == cid]

    def talks_to(self, cid: str) -> str:
        """'basket-api (gRPC), redis' — what one box calls, for tables and prompts."""
        return ", ".join(f"{self.name_of(l.target)} ({l.label})" if l.label else self.name_of(l.target)
                         for l in self.outgoing(cid))

    def label_for(self, c: Component, labels: dict[str, str]) -> str:
        return labels.get(c.id, c.kind)

    def signature(self) -> str:
        """Structure only (boxes + arrows), no labels: equal signature = nothing to redraw."""
        return json.dumps({"n": [(c.id, c.kind) for c in self.components],
                           "e": [(l.source, l.target, l.label, l.dotted) for l in self.links]})
