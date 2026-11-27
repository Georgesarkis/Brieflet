"""ComponentScanner for .NET Aspire: the component graph from the AppHost + each project's code (no LLM, no build).

- AppHost (*.csproj with Aspire.Hosting.AppHost / Aspire.AppHost.Sdk): `builder.AddProject<Projects.X>("name")`,
  `AddDotnetProject("name", "../Path")`, `AddRedis/AddRabbitMQ/AddPostgres/AddYarp/...("name")`, `pg.AddDatabase("db")`,
  `.WithReference(x)`, `.WithEnvironment("...Url", x.GetEndpoint(..))`, custom calls like `.ConfigureMobileBffRoutes(a, b)`
- each project's .csproj (ProjectReferences, PackageReferences) and HTTP/gRPC client registrations (edge protocol)
Boxes = AppHost resources only (max ~15), never classes.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from ...domain.components import MAX_BOXES, Component, ComponentGraph
from .apphost_statements import AppHostReader

CLIENT_RE = re.compile(r'(AddGrpcClient|AddHttpClient|MapForwarder)\b[^;]*?"(?:https?\+?)?(?:https?)?://([a-z0-9-]+)', re.S)
DEFAULT_LABEL = {"queue": "events", "cache": "cache", "database": "db"}


def strip_comments(code: str) -> str:
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"])//.*$", r"\1", code)


def find_apphost(snapshot) -> str | None:
    """Folder of the AppHost project (shortest path wins: src/eShop.AppHost over tests/*AppHost)."""
    hits = [str(PurePosixPath(f).parent) for f in snapshot.files if f.endswith(".csproj")
            and any(s in (snapshot.read(f) or "") for s in ("Aspire.Hosting.AppHost", "Aspire.AppHost.Sdk"))]
    hits.sort(key=lambda d: (d.startswith("test"), "test" in d.lower(), len(d)))
    return hits[0] if hits else None


def _cs_files(snapshot, folder: str):
    return [f for f in snapshot.files if f.startswith(folder + "/") and f.endswith(".cs") and "/obj/" not in f]


class AspireScanner:
    def scan(self, snapshot) -> ComponentGraph:
        apphost = find_apphost(snapshot)
        if not apphost:
            return ComponentGraph(None)
        code = "\n".join(strip_comments(snapshot.read(f) or "") for f in sorted(_cs_files(snapshot, apphost))
                         if PurePosixPath(f).name in ("AppHost.cs", "Program.cs"))
        reader = AppHostReader(snapshot, apphost)
        reader.read(code)
        refs = {c.id: self._read_project(snapshot, c, reader) for c in reader.nodes.values() if c.path}
        for link in reader.links.values():
            link.label = link.label or DEFAULT_LABEL.get(reader.nodes[link.target].kind, "")
        order = list(reader.nodes)
        links = sorted(reader.links.values(), key=lambda l: (order.index(l.source), order.index(l.target)))
        return ComponentGraph(apphost, list(reader.nodes.values())[:MAX_BOXES], links,
                              {k: v for k, v in refs.items() if v is not None})

    @staticmethod
    def _read_project(snapshot, c: Component, reader: AppHostReader) -> list[str] | None:
        """Protocol labels from the project's own client registrations; → its ProjectReferences (None: no csproj)."""
        by_name = {n.name: n.id for n in reader.nodes.values()}
        src = "\n".join(snapshot.read(f) or "" for f in _cs_files(snapshot, c.path))
        for call, host in CLIENT_RE.findall(src):
            if host in by_name:
                reader.set_protocol(c.id, by_name[host], "gRPC" if call == "AddGrpcClient" else "HTTP")
        csproj = next((f for f in snapshot.files if f.startswith(c.path + "/") and f.endswith(".csproj")
                       and f.count("/") == c.path.count("/") + 1), None)
        if not csproj:
            return None
        xml = snapshot.read(csproj) or ""
        c.packages = re.findall(r'PackageReference\s+Include="([^"]+)"', xml)[:12]
        return sorted({PurePosixPath(r.replace("\\", "/")).stem for r in re.findall(r'ProjectReference\s+Include="([^"]+)"', xml)})
