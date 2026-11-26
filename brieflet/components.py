"""Brieflet: the high-level component diagram of a .NET Aspire repo, from plain code (no LLM).

Sources, all read at one commit through git (no checkout, no build):
- the AppHost (*.csproj with Aspire.Hosting.AppHost / Aspire.AppHost.Sdk): `builder.AddDotnetProject("name", "../Path")`,
  `AddProject<Projects.X>("name")`, `AddRedis/AddRabbitMQ/AddPostgres/AddYarp/...("name")`, `pg.AddDatabase("db")`,
  `.WithReference(x)`, `.WithEnvironment("...Url", x.GetEndpoint(..))`, custom calls like `.ConfigureMobileBffRoutes(a, b)`
- each project's .csproj ProjectReferences (shown in the table, not as boxes) and its HTTP/gRPC client registrations
  (`AddGrpcClient<..>(.. "http://basket-api")` → edge label gRPC, `AddHttpClient<..>(.. "://catalog-api")` → HTTP)
Boxes = AppHost resources only (max ~15), never classes. The LLM only writes the short box labels; labels already
in the committed components.md are reused, so an unchanged structure gives a byte-identical file (= no diff).
"""
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

INFRA = {  # Add<Method> → (kind, mermaid shape)
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
CLIENT_RE = re.compile(r'(AddGrpcClient|AddHttpClient|MapForwarder)\b[^;]*?"(?:https?\+?)?(?:https?)?://([a-z0-9-]+)', re.S)
MAX_BOXES = 15


class Tree:
    """Read-only view of a repo at one commit."""
    def __init__(self, repo: Path, rev: str):
        self.repo, self.rev = Path(repo), rev
        r = self._git("ls-tree", "-r", "--name-only", rev)
        self.files = r.splitlines()
        self._set = set(self.files)
        self._cache: dict[str, str | None] = {}

    def _git(self, *a) -> str:
        r = subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError(f"git {a[0]}: {r.stderr.strip()[-200:]}")
        return r.stdout

    def has(self, path: str) -> bool:
        return path in self._set

    def has_dir(self, d: str) -> bool:
        d = d.rstrip("/") + "/"
        return any(f.startswith(d) for f in self.files)

    def read(self, path: str) -> str | None:
        if path not in self._cache:
            if path not in self._set:
                self._cache[path] = None
            else:
                r = subprocess.run(["git", "-C", str(self.repo), "show", f"{self.rev}:{path}"], capture_output=True, timeout=60)
                self._cache[path] = r.stdout.decode("utf-8", "replace").lstrip("﻿") if r.returncode == 0 else None
        return self._cache[path]


def strip_comments(code: str) -> str:
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"])//.*$", r"\1", code)


def find_apphost(t: Tree) -> str | None:
    """Folder of the AppHost project (shortest path wins: src/eShop.AppHost over tests/*AppHost)."""
    hits = []
    for f in t.files:
        if f.endswith(".csproj"):
            txt = t.read(f) or ""
            if "Aspire.Hosting.AppHost" in txt or "Aspire.AppHost.Sdk" in txt:
                hits.append(str(PurePosixPath(f).parent))
    hits.sort(key=lambda d: (d.startswith("test"), "test" in d.lower(), len(d)))
    return hits[0] if hits else None


def _norm(p: str) -> str:
    parts = []
    for x in p.split("/"):
        if x in ("", "."):
            continue
        if x == "..":
            if parts:
                parts.pop()
        else:
            parts.append(x)
    return "/".join(parts)


def _project_dir(t: Tree, apphost: str, rel: str | None, proj_type: str | None) -> str | None:
    if rel:
        d = _norm(f"{apphost}/{rel}")
        if d.endswith(".csproj"):
            d = str(PurePosixPath(d).parent)
        return d if t.has_dir(d) else None
    if proj_type:  # Projects.Basket_API → a folder whose csproj is Basket.API.csproj
        want = proj_type.replace("_", ".").lower()
        for f in t.files:
            if f.endswith(".csproj") and PurePosixPath(f).stem.lower() == want:
                return str(PurePosixPath(f).parent)
    return None


def node_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", name).lower()


def parse(t: Tree) -> dict:
    """→ {"apphost", "nodes": [{id, name, kind, shape, path}], "edges": [{a, b, label, dotted}], "refs": {id: [..]}}"""
    apphost = find_apphost(t)
    if not apphost:
        return {"apphost": None, "nodes": [], "edges": [], "refs": {}}
    code = "\n".join(strip_comments(t.read(f) or "") for f in sorted(t.files)
                     if f.startswith(apphost + "/") and f.endswith(".cs") and "/obj/" not in f
                     and PurePosixPath(f).name in ("AppHost.cs", "Program.cs"))
    stmts = [s.strip() for s in code.split(";") if s.strip()]
    nodes, var, endpoint = {}, {}, {}  # id → node, var → id, endpoint var → id
    edges = {}

    def add_edge(a, b, label="", dotted=False):
        if a and b and a != b:
            k = (a, b)
            if k not in edges or (edges[k]["dotted"] and not dotted):
                edges[k] = {"a": a, "b": b, "label": label, "dotted": dotted}

    for s in stmts:
        target = None
        if m := PROJECT_RE.match(s):
            v, ptype, name, rel = m.groups()
            nid = node_id(name)
            nodes.setdefault(nid, {"id": nid, "name": name, "kind": "service", "shape": "box",
                                   "path": _project_dir(t, apphost, rel, ptype)})
            target = nid
        elif (m := INFRA_RE.match(s)) and m.group(2) in INFRA:
            v, meth, name = m.groups()
            nid = node_id(name)
            kind, shape = INFRA[meth]
            nodes.setdefault(nid, {"id": nid, "name": name, "kind": kind, "shape": shape, "path": None,
                                   "tech": meth[3:]})
            target = nid
        elif m := DB_RE.match(s):
            v, parent, db = m.groups()
            if parent in var:
                var[v] = var[parent]
                nodes[var[parent]].setdefault("dbs", {})[v] = db
            continue
        elif m := ENDPOINT_RE.match(s):
            v, src = m.groups()
            if src in var:
                endpoint[v] = var[src]
            continue
        elif (m := TARGET_RE.match(s)) and m.group(1) in var:
            target = var[m.group(1)]
            v = None
        else:
            continue
        if v:
            var[v] = target
        for meth, args in CALL_RE.findall(s):
            names = re.findall(r"\b(\w+)\b", args)
            if meth == "WithReference" and names and names[0] in var:
                ref = names[0]
                tgt = var[ref]
                db = nodes[tgt].get("dbs", {}).get(ref, "")
                add_edge(target, tgt, db)
            elif meth == "WithEnvironment":
                envname = (re.findall(r'"([^"]+)"', args) or [""])[0]
                if "url" in envname.lower() and "callback" not in envname.lower():
                    for n in names:
                        if n in endpoint:
                            add_edge(target, endpoint[n], "auth" if "ident" in envname.lower() else "url", dotted=True)
            elif meth.startswith("Configure"):
                for n in names:
                    if n in var:
                        add_edge(target, var[n], "routes")

    # protocol labels from the projects' own client registrations
    by_name = {n["name"]: n["id"] for n in nodes.values()}
    refs = {}
    for n in nodes.values():
        if not n.get("path"):
            continue
        src = "\n".join(t.read(f) or "" for f in t.files
                        if f.startswith(n["path"] + "/") and f.endswith(".cs") and "/obj/" not in f)
        for call, host in CLIENT_RE.findall(src):
            if host in by_name:
                proto = "gRPC" if call == "AddGrpcClient" else "HTTP"
                k = (n["id"], by_name[host])
                if k in edges and not edges[k]["dotted"]:
                    edges[k]["label"] = proto if edges[k]["label"] in ("", "routes") else edges[k]["label"]
                else:
                    add_edge(n["id"], by_name[host], proto)
        csproj = next((f for f in t.files if f.startswith(n["path"] + "/") and f.endswith(".csproj")
                       and f.count("/") == n["path"].count("/") + 1), None)
        if csproj:
            refs[n["id"]] = sorted({PurePosixPath(r.replace("\\", "/")).stem for r in
                                    re.findall(r'ProjectReference\s+Include="([^"]+)"', t.read(csproj) or "")})
            n["packages"] = re.findall(r'PackageReference\s+Include="([^"]+)"', t.read(csproj) or "")[:12]
    for e in edges.values():  # default labels by target kind
        if not e["label"]:
            e["label"] = {"queue": "events", "cache": "cache", "database": "db"}.get(nodes[e["b"]]["kind"], "")
    order = list(nodes)
    return {"apphost": apphost, "nodes": [nodes[i] for i in order][:MAX_BOXES],
            "edges": sorted(edges.values(), key=lambda e: (order.index(e["a"]), order.index(e["b"]))),
            "refs": refs}


def signature(comp: dict) -> str:
    """Structure only (boxes + arrows), no labels: equal signature = nothing to redraw."""
    return json.dumps({"n": [(n["id"], n["kind"]) for n in comp["nodes"]],
                       "e": [(e["a"], e["b"], e["label"], e["dotted"]) for e in comp["edges"]]})


LABEL_LINE_RE = re.compile(r'^\s+(\w+)(?:\[\(|\[\[|\{\{|\[)"([^"<]+)<br/>([^"]*)"')


def labels_from(md: str | None) -> dict:
    """Labels already in a committed components.md: {id: label}."""
    out = {}
    for l in (md or "").splitlines():
        if m := LABEL_LINE_RE.match(l):
            out[m.group(1)] = m.group(3)
    return out


def clean_label(s) -> str:
    s = re.sub(r'["<>\[\]{}()|`#]', "", str(s or "")).strip()
    return " ".join(s.split()[:5])[:40]


SHAPES = {"box": ('["', '"]'), "db": ('[("', '")]'), "queue": ('[["', '"]]'), "hex": ('{{"', '"}}')}


def mermaid(comp: dict, labels: dict) -> str:
    out = ["flowchart LR"]
    infra = [n for n in comp["nodes"] if n["kind"] in ("cache", "queue", "database")]
    for n in comp["nodes"]:
        if n in infra:
            continue
        a, b = SHAPES[n["shape"]]
        out.append(f'    {n["id"]}{a}{n["name"]}<br/>{labels.get(n["id"], n["kind"])}{b}')
    if infra:
        out.append('    subgraph infra["Infrastructure"]')
        for n in infra:
            a, b = SHAPES[n["shape"]]
            out.append(f'        {n["id"]}{a}{n["name"]}<br/>{labels.get(n["id"], n["kind"])}{b}')
        out.append("    end")
    for e in comp["edges"]:
        arrow = "-.->" if e["dotted"] else "-->"
        lab = f'|{e["label"]}|' if e["label"] else ""
        out.append(f'    {e["a"]} {arrow}{lab} {e["b"]}')
    return "\n".join(out)


def render(comp: dict, labels: dict) -> str:
    """The whole docs/architecture/components.md."""
    rows = []
    names = {n["id"]: n["name"] for n in comp["nodes"]}
    for n in comp["nodes"]:
        talks = ", ".join(f'{names[e["b"]]} ({e["label"]})' if e["label"] else names[e["b"]]
                          for e in comp["edges"] if e["a"] == n["id"]) or "—"
        where = f'`{n["path"]}`' if n.get("path") else n.get("tech", n["kind"])
        libs = ", ".join(comp["refs"].get(n["id"], [])) or "—"
        rows.append(f'| {n["name"]} | {labels.get(n["id"], n["kind"])} | {where} | {talks} | {libs} |')
    return "\n".join([
        "# Components",
        "",
        f"Generated by Brieflet from `{comp['apphost']}`, the project files and the HTTP/gRPC client registrations. "
        "Change the code, not this file. Solid arrow = calls / uses, dotted = gets a URL (auth).",
        "",
        "```mermaid",
        mermaid(comp, labels),
        "```",
        "",
        "| Box | What it is | Where | Talks to | Uses libraries |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ])
