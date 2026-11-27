"""ComponentScanner for any language: boxes from package manifests, Docker Compose, Dockerfiles and entry points.

Used when a repo has no .NET Aspire AppHost. No build, no package manager, no LLM.
- each manifest folder (package.json, pyproject.toml, go.mod, Cargo.toml, pom.xml, *.csproj, …) = a project;
  it is a *service* when it runs (Dockerfile, entry point, start script, web framework dependency), else a *library*
- compose services = boxes too (built ones map onto their project); known images (postgres, redis, …) = infrastructure
- arrows: compose depends_on + URLs in compose environment, internal dependencies between projects,
  client libraries (pg, ioredis, kafkajs, …) → an infrastructure box
- no manifests at all: the top code folders are the boxes
Big repos (100+ packages) are cut to MAX_BOXES: the most used / deployable projects stay, the rest become one
group box per parent folder ("packages/*").
"""
from __future__ import annotations

from ...domain.components import MAX_BOXES, Component, ComponentGraph, Link
from .compose import read_services
from .grouping import collapse
from .manifests import Project, main_part, norm, read_projects, skipped
from .tech import INFRA, client_tech, image_tech

CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".go", ".rs", ".java", ".kt", ".cs", ".rb", ".php", ".swift",
            ".c", ".cc", ".cpp", ".h", ".scala", ".ex", ".exs", ".dart", ".vue", ".svelte")
LANG_NAME = {"javascript": "JavaScript", "typescript": "TypeScript", "python": "Python", "go": "Go", "rust": "Rust",
             "java": "Java", "csharp": "C#", "fsharp": "F#", "php": "PHP", "ruby": "Ruby"}
DEFAULT_LABEL = {"queue": "events", "cache": "cache", "database": "db"}


def node_id(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.lstrip("@")).lower().strip("_") or "root"


class WorkspaceScanner:
    def scan(self, snapshot) -> ComponentGraph:
        notes: list[str] = []
        projects = _real_projects(read_projects(snapshot))
        services = read_services(snapshot, notes)
        g = _Builder()
        for s in services:
            g.add_service(s, projects)
        for p in projects:
            g.add_project(p)
        g.link_projects(projects)
        for s in services:
            g.link_service(s)
        if not g.nodes:
            g.add_folders(snapshot)
        comps, links = list(g.nodes.values()), list(g.links.values())
        if len(comps) > MAX_BOXES:
            comps, links, refs = collapse(comps, links, g.refs, MAX_BOXES, _code_files(snapshot, comps))
            notes.append(f"{len(g.nodes)} parts found; diagram keeps {MAX_BOXES} boxes, the rest are grouped by folder")
        else:
            refs = g.refs
        for l in links:
            target = next(c for c in comps if c.id == l.target)
            l.label = l.label or DEFAULT_LABEL.get(target.kind, "")
        origin = " and ".join(x for x in ("the package manifests" if projects else "the top code folders",
                                          "Docker Compose" if services else "") if x)
        graph = ComponentGraph(None, comps, links, refs, f"{origin}, Dockerfiles and the projects' dependencies")
        graph.notes = notes
        return graph


def _code_files(snapshot, comps: list[Component]) -> dict[str, int]:
    """Code files under each project folder (nested projects counted in their parent too)."""
    code = [f for f in snapshot.files if f.endswith(CODE_EXT) and not skipped(f)]
    out = {}
    for c in comps:
        if c.path is not None:
            pre = "" if c.path in ("", ".") else c.path.rstrip("/") + "/"
            out[c.id] = sum(1 for f in code if f.startswith(pre))
    return out


def _real_projects(projects: list[Project]) -> list[Project]:
    """Drop the workspace root (it only lists the others) and example/test-only projects when there are real ones."""
    return main_part([p for p in projects if not (p.workspace_root and len(projects) > 1)], lambda p: p.dir)


class _Builder:
    def __init__(self):
        self.nodes: dict[str, Component] = {}
        self.links: dict[tuple[str, str], Link] = {}
        self.by_dir: dict[str, str] = {}          # project folder → component id
        self.by_service: dict[str, str] = {}      # compose service name → component id
        self.refs: dict[str, list[str]] = {}

    def _add(self, c: Component) -> str:
        while c.id in self.nodes:
            c.id += "_2"
        self.nodes[c.id] = c
        return c.id

    def link(self, a: str | None, b: str | None, label: str = "") -> None:
        if a and b and a != b and (a, b) not in self.links:
            self.links[(a, b)] = Link(a, b, label)

    def infra(self, tech: str, name: str | None = None) -> str:
        found = next((c.id for c in self.nodes.values() if c.tech == tech and c.path is None), None)
        if found:
            return found
        kind, shape = INFRA[tech]
        return self._add(Component(node_id(name or tech), name or tech.lower(), kind, shape, None, tech))

    def add_service(self, s, projects: list[Project]) -> None:
        if s.build is not None:
            p = None if s.side else _project_for(s.build, projects)
            cid = self._add(Component(node_id(s.name), s.name, "service", "box", p.dir or "." if p else s.build or ".",
                                      LANG_NAME.get(p.lang) if p else None))
            if p:
                self.by_dir[p.dir] = cid
                self._fill(self.nodes[cid], p)
        elif tech := image_tech(s.image):
            cid = self.infra(tech, s.name)
        else:
            cid = self._add(Component(node_id(s.name), s.name, "container", "box", None, s.image.split(":")[0] or None))
        self.by_service[s.name] = cid

    def add_project(self, p: Project) -> None:
        if p.dir in self.by_dir:
            return
        name = p.name if p.dir or p.name != "root" else "app"
        if any(c.name == name for c in self.nodes.values()):        # two packages called "turbo": say which
            name = f"{name} ({p.dir or '.'})"
        c = Component(node_id(name), name, "service" if p.runs else "library", "box", p.dir or ".", LANG_NAME.get(p.lang))
        self.by_dir[p.dir] = self._add(c)
        self._fill(c, p)

    @staticmethod
    def _fill(c: Component, p: Project) -> None:
        c.packages = [d for d in p.deps if not d.startswith("@types/")][:12]
        c.entry = p.entry
        if p.runs and c.kind == "library":
            c.kind = "service"

    def link_projects(self, projects: list[Project]) -> None:
        by_key = {p.key: p.dir for p in projects}
        for p in projects:
            src = self.by_dir.get(p.dir)
            dirs = [by_key[norm(d)] for d in p.deps if norm(d) in by_key and by_key[norm(d)] != p.dir]
            dirs += [d for d in p.refs if d in self.by_dir]
            for d in dict.fromkeys(dirs):
                self.link(src, self.by_dir.get(d))
            names = [self.nodes[self.by_dir[d]].name for d in dict.fromkeys(dirs) if d in self.by_dir]
            if src and names:
                self.refs[src] = sorted(names)
            for tech in dict.fromkeys(t for d in p.deps if (t := client_tech(d))):
                self.link(src, self.infra(tech))

    def link_service(self, s) -> None:
        src = self.by_service.get(s.name)
        for host, proto in s.calls.items():
            self.link(src, self.by_service.get(host), proto)
        for d in s.depends_on:
            self.link(src, self.by_service.get(d))

    def add_folders(self, snapshot) -> None:
        """No manifests, no compose: one box per top code folder (under src/ when that is where the code is)."""
        code = [f for f in snapshot.files if f.endswith(CODE_EXT) and not skipped(f)]
        src = [f for f in code if f.startswith("src/") and f.count("/") >= 2]
        pick = src if len(src) * 2 >= len(code) else code
        depth = 2 if pick is src else 1
        counts: dict[str, int] = {}
        for f in pick:
            if f.count("/") >= depth:
                d = "/".join(f.split("/")[:depth])
                counts[d] = counts.get(d, 0) + 1
        for d, _ in sorted(counts.items(), key=lambda x: -x[1])[: MAX_BOXES * 4]:
            self._add(Component(node_id(d.split("/")[-1]), d.split("/")[-1], "module", "box", d))


def _project_for(build: str, projects: list[Project]) -> Project | None:
    """The project a compose build context builds: same folder, else the only project inside it."""
    exact = next((p for p in projects if p.dir == build), None)
    if exact:
        return exact
    inside = [p for p in projects if build == "" or p.dir.startswith(build + "/")]
    return inside[0] if len(inside) == 1 else None
