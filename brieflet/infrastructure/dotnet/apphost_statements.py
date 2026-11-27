"""Reads AppHost statements one by one into components and links (a tiny C# statement reader, not a parser)."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from ...domain.components import Component, Link

INFRA = {  # Add<Method> → (kind, diagram shape)
    "AddRedis": ("cache", "db"), "AddGarnet": ("cache", "db"), "AddValkey": ("cache", "db"),
    "AddRabbitMQ": ("queue", "queue"), "AddKafka": ("queue", "queue"), "AddAzureServiceBus": ("queue", "queue"),
    "AddPostgres": ("database", "db"), "AddSqlServer": ("database", "db"), "AddMySql": ("database", "db"),
    "AddMongoDB": ("database", "db"), "AddAzureCosmosDB": ("database", "db"),
    "AddYarp": ("proxy", "hex"), "AddContainer": ("container", "box"), "AddKeycloak": ("auth", "box"),
}
PROJECT_RE = re.compile(r'^(?:var\s+(\w+)\s*=\s*)?builder\s*\.\s*Add(?:Dotnet)?Project\s*(?:<\s*Projects\.(\w+)\s*>)?\s*\(\s*"([^"]+)"'
                        r'(?:\s*,\s*"([^"]+)")?', re.S)
INFRA_RE = re.compile(r'^(?:var\s+(\w+)\s*=\s*)?builder\s*\.\s*(Add\w+)\s*\(\s*"([^"]+)"', re.S)
DB_RE = re.compile(r'^var\s+(\w+)\s*=\s*(\w+)\s*\.\s*AddDatabase\s*\(\s*"([^"]+)"', re.S)
ENDPOINT_RE = re.compile(r'^var\s+(\w+)\s*=\s*(\w+)\s*\.\s*GetEndpoint\s*\(', re.S)
TARGET_RE = re.compile(r'^(\w+)\s*\.', re.S)
CALL_RE = re.compile(r'\.\s*(\w+)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)', re.S)


def node_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", name).lower()


def normalize(path: str) -> str:
    parts: list[str] = []
    for x in path.split("/"):
        if x == "..":
            if parts:
                parts.pop()
        elif x not in ("", "."):
            parts.append(x)
    return "/".join(parts)


class AppHostReader:
    def __init__(self, snapshot, apphost: str):
        self.snapshot, self.apphost = snapshot, apphost
        self.nodes: dict[str, Component] = {}
        self.links: dict[tuple[str, str], Link] = {}
        self.var: dict[str, str] = {}        # C# variable → component id
        self.endpoint: dict[str, str] = {}   # endpoint variable → component id

    def read(self, code: str) -> None:
        for s in (s.strip() for s in code.split(";")):
            if s:
                self._statement(s)

    def link(self, a: str | None, b: str | None, label: str = "", dotted: bool = False) -> None:
        if a and b and a != b:
            k = (a, b)
            if k not in self.links or (self.links[k].dotted and not dotted):
                self.links[k] = Link(a, b, label, dotted)

    def set_protocol(self, a: str, b: str, proto: str) -> None:
        k = (a, b)
        if k in self.links and not self.links[k].dotted:
            if self.links[k].label in ("", "routes"):
                self.links[k].label = proto
        else:
            self.link(a, b, proto)

    def _statement(self, s: str) -> None:
        target, v = self._declaration(s)
        if target is None:
            return
        if v:
            self.var[v] = target
        for meth, args in CALL_RE.findall(s):
            self._call(target, meth, args)

    def _declaration(self, s: str) -> tuple[str | None, str | None]:
        """→ (component this statement configures, variable it assigns)."""
        if m := PROJECT_RE.match(s):
            v, ptype, name, rel = m.groups()
            nid = node_id(name)
            self.nodes.setdefault(nid, Component(nid, name, "service", "box", self._project_dir(rel, ptype)))
            return nid, v
        if (m := INFRA_RE.match(s)) and m.group(2) in INFRA:
            v, meth, name = m.groups()
            nid = node_id(name)
            kind, shape = INFRA[meth]
            self.nodes.setdefault(nid, Component(nid, name, kind, shape, None, meth[3:]))
            return nid, v
        if m := DB_RE.match(s):
            v, parent, db = m.groups()
            if parent in self.var:
                self.var[v] = self.var[parent]
                self.nodes[self.var[parent]].databases[v] = db
            return None, None
        if m := ENDPOINT_RE.match(s):
            v, src = m.groups()
            if src in self.var:
                self.endpoint[v] = self.var[src]
            return None, None
        if (m := TARGET_RE.match(s)) and m.group(1) in self.var:
            return self.var[m.group(1)], None
        return None, None

    def _call(self, target: str, meth: str, args: str) -> None:
        names = re.findall(r"\b(\w+)\b", args)
        if meth == "WithReference" and names and names[0] in self.var:
            ref = self.var[names[0]]
            self.link(target, ref, self.nodes[ref].databases.get(names[0], ""))
        elif meth == "WithEnvironment":
            env = (re.findall(r'"([^"]+)"', args) or [""])[0].lower()
            if "url" in env and "callback" not in env:
                for n in names:
                    if n in self.endpoint:
                        self.link(target, self.endpoint[n], "auth" if "ident" in env else "url", dotted=True)
        elif meth.startswith("Configure"):
            for n in names:
                if n in self.var:
                    self.link(target, self.var[n], "routes")

    def _project_dir(self, rel: str | None, proj_type: str | None) -> str | None:
        if rel:
            d = normalize(f"{self.apphost}/{rel}")
            d = str(PurePosixPath(d).parent) if d.endswith(".csproj") else d
            return d if self.snapshot.has_dir(d) else None
        if proj_type:  # Projects.Basket_API → a folder whose csproj is Basket.API.csproj
            want = proj_type.replace("_", ".").lower()
            for f in self.snapshot.files:
                if f.endswith(".csproj") and PurePosixPath(f).stem.lower() == want:
                    return str(PurePosixPath(f).parent)
        return None
