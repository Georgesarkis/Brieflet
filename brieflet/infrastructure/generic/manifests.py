"""Package manifests of any language → Project records (name, folder, dependencies, does it run).

One reader per manifest type: package.json, pyproject.toml / setup.py / setup.cfg / requirements.txt, go.mod,
Cargo.toml, pom.xml, build.gradle(.kts), *.csproj / *.fsproj, composer.json, Gemfile. No build, no package manager, no network.
"""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import PurePosixPath

SKIP_DIRS = {"node_modules", "vendor", "third_party", "dist", "build", "out", "target", "bin", "obj", ".git",
             ".venv", "venv", "__pycache__", "site-packages", "fixtures", "testdata", "__fixtures__", ".next"}
MANIFESTS = ("package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "go.mod", "Cargo.toml",
             "pom.xml", "build.gradle", "build.gradle.kts", "*.csproj", "composer.json", "Gemfile")
RUNNERS = {  # a dependency that means "this project is something that runs", not a library
    "express", "fastify", "koa", "@nestjs/core", "next", "nuxt", "@remix-run/node", "@sveltejs/kit", "vite",
    "react-scripts", "@angular/core", "hono", "electron", "fastapi", "flask", "django", "starlette", "aiohttp",
    "uvicorn", "gunicorn", "celery", "streamlit", "gin-gonic/gin", "labstack/echo", "gofiber/fiber", "actix-web",
    "axum", "rocket", "spring-boot-starter-web", "spring-boot-starter-webflux", "rails", "sinatra", "laravel/framework",
}
ENTRY_FILES = ("__main__.py", "manage.py", "main.py", "app.py", "wsgi.py", "asgi.py", "server.py", "main.go",
               "src/main.rs", "Program.cs", "server.js", "server.ts", "index.js", "main.ts", "main.js")
SIDE_DIRS = {"examples", "example", "samples", "sample", "test", "tests", "__tests__", "e2e", "docs", "benchmarks",
             "bench", "templates", "template", "demo", "demos", "playground", "scripts"}
DEP_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass
class Project:
    dir: str                                   # "" = repo root
    name: str
    lang: str
    manifest: str
    deps: list[str] = field(default_factory=list)
    runs: bool = False                         # app/service/CLI, not only a library
    entry: str | None = None                   # first entry point file found
    dockerfile: str | None = None
    workspace_root: bool = False               # only lists other projects (npm workspaces, uv/cargo workspace, …)
    refs: list[str] = field(default_factory=list)   # internal project dirs it depends on by path (.csproj)
    runtime_deps: list[str] | None = None      # deps without dev-only ones, when the manifest tells them apart

    @property
    def key(self) -> str:
        return norm(self.name)


def normalize(path: str) -> str:
    """'src/Web/../ApplicationCore/x.csproj' → 'src/ApplicationCore/x.csproj'."""
    parts: list[str] = []
    for x in path.split("/"):
        if x == "..":
            if parts:
                parts.pop()
        elif x not in ("", "."):
            parts.append(x)
    return "/".join(parts)


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.lower())


def skipped(path: str) -> bool:
    return any(p in SKIP_DIRS or p.startswith(".") and p not in (".github",) for p in path.split("/")[:-1])


def side(path: str) -> bool:
    """Examples, tests, docs, templates: real code, but not the system itself."""
    return any(p in SIDE_DIRS or p.startswith(("example", "sample", "demo")) for p in path.split("/"))


def main_part(items: list, path_of=lambda x: x) -> list:
    """Items outside example/test/doc folders; all items when that leaves none."""
    core = [x for x in items if not side(path_of(x))]
    return core or items


def read_projects(snapshot) -> list[Project]:
    """One Project per folder (first manifest wins in MANIFESTS order), root workspaces flagged."""
    by_dir: dict[str, Project] = {}
    for f in sorted((f for f in snapshot.files if manifest_kind(f) and not skipped(f)),
                    key=lambda f: MANIFESTS.index(manifest_kind(f))):
        d = str(PurePosixPath(f).parent) if "/" in f else ""
        if d in by_dir:
            by_dir[d].deps += [x for x in _read(snapshot, f, d).deps if x not in by_dir[d].deps]
            continue
        p = _read(snapshot, f, d)
        if p.lang == "python" and PurePosixPath(f).name == "requirements.txt" and not _has(snapshot, d, ".py"):
            continue
        if p.lang == "javascript" and snapshot.has(f"{d}/tsconfig.json".lstrip("/")):
            p.lang = "typescript"
        by_dir[d] = p
    for p in by_dir.values():
        p.entry = next((f"{p.dir}/{e}".lstrip("/") for e in ENTRY_FILES if snapshot.has(f"{p.dir}/{e}".lstrip("/"))),
                       p.entry)
        p.dockerfile = next((f for f in (f"{p.dir}/Dockerfile".lstrip("/"),) if snapshot.has(f)), None)
        runtime = p.deps if p.runtime_deps is None else p.runtime_deps
        p.runs = p.runs or bool(p.dockerfile) or any(is_runner(x) for x in runtime) or _entry_runs(p)
    return list(by_dir.values())


def manifest_kind(f: str) -> str | None:
    """'src/Api/Api.csproj' → '*.csproj'; 'a/package.json' → 'package.json'; else None."""
    name = PurePosixPath(f).name
    if name in MANIFESTS:
        return name
    return "*.csproj" if name.endswith((".csproj", ".fsproj")) else None


def is_runner(dep: str) -> bool:
    d = dep.lower()
    return d in RUNNERS or any(d.endswith("/" + r) for r in RUNNERS if "/" in r and not r.startswith("@"))


def _entry_runs(p: Project) -> bool:
    return bool(p.entry) and PurePosixPath(p.entry).name not in ("index.js", "main.js", "main.ts")


def _has(snapshot, d: str, ext: str) -> bool:
    pre = f"{d}/" if d else ""
    return any(f.startswith(pre) and f.endswith(ext) and f.count("/") <= pre.count("/") + 2 for f in snapshot.files)


def _read(snapshot, f: str, d: str) -> Project:
    text = snapshot.read(f) or ""
    kind = manifest_kind(f) or ""
    folder = PurePosixPath(d).name or "root"
    reader = READERS.get(kind) or (_gradle if kind.startswith("build.gradle") else None)
    try:
        return reader(text, d, f, folder)
    except (ValueError, TypeError, AttributeError, tomllib.TOMLDecodeError):
        return Project(d, folder, LANG.get(kind, "?"), f)


def _package_json(text, d, f, folder) -> Project:
    j = json.loads(text)
    deps = [*j.get("dependencies", {}), *j.get("devDependencies", {}), *j.get("peerDependencies", {})]
    scripts = j.get("scripts") or {}
    runs = bool(j.get("bin")) or any(k in scripts for k in ("start", "serve"))
    p = Project(d, str(j.get("name") or folder), "javascript", f, deps, runs)
    p.runtime_deps = list(j.get("dependencies") or {})
    p.workspace_root = bool(j.get("workspaces")) and not d
    return p


def _pyproject(text, d, f, folder) -> Project:
    t = tomllib.loads(text)
    proj = t.get("project") or {}
    poetry = (t.get("tool") or {}).get("poetry") or {}
    deps = [m.group(1) for x in proj.get("dependencies") or [] if (m := DEP_NAME.match(x))]
    deps += [k for k in (poetry.get("dependencies") or {}) if k.lower() != "python"]
    for group in (proj.get("optional-dependencies") or {}).values():
        deps += [m.group(1) for x in group if (m := DEP_NAME.match(x))]
    runs = bool(proj.get("scripts") or poetry.get("scripts"))
    p = Project(d, str(proj.get("name") or poetry.get("name") or folder), "python", f, list(dict.fromkeys(deps)), runs)
    p.workspace_root = not d and bool(((t.get("tool") or {}).get("uv") or {}).get("workspace")) and not proj.get("dependencies")
    return p


def _setup_py(text, d, f, folder) -> Project:
    m = re.search(r"name\s*=\s*['\"]([^'\"]+)", text)
    deps = re.findall(r"['\"]([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:[<>=!~;\[][^'\"]*)?['\"]",
                      (re.search(r"install_requires\s*=\s*\[(.*?)\]", text, re.S) or [None, ""])[1])
    return Project(d, m.group(1) if m else folder, "python", f, deps, "entry_points" in text)


def _requirements(text, d, f, folder) -> Project:
    deps = [m.group(1) for l in text.splitlines() if not l.strip().startswith(("#", "-")) and (m := DEP_NAME.match(l))]
    return Project(d, folder, "python", f, deps)


def _go_mod(text, d, f, folder) -> Project:
    m = re.search(r"^module\s+(\S+)", text, re.M)
    deps = re.findall(r"^\s*(?:require\s+)?([a-z0-9.-]+\.[a-z]+/\S+)\s+v", text, re.M)
    return Project(d, m.group(1) if m else folder, "go", f, deps)


def _cargo(text, d, f, folder) -> Project:
    t = tomllib.loads(text)
    deps = [*(t.get("dependencies") or {}), *(t.get("dev-dependencies") or {})]
    pkg = t.get("package") or {}
    p = Project(d, str(pkg.get("name") or folder), "rust", f, deps, bool(t.get("bin")))
    p.workspace_root = not pkg and bool(t.get("workspace"))
    return p


def _pom(text, d, f, folder) -> Project:
    body = re.sub(r"<parent>.*?</parent>", "", text, flags=re.S)
    m = re.search(r"<artifactId>([^<]+)</artifactId>", body)
    deps = re.findall(r"<dependency>.*?<artifactId>([^<]+)</artifactId>", body, re.S)
    p = Project(d, m.group(1) if m else folder, "java", f, deps)
    p.workspace_root = "<modules>" in body and not deps
    return p


def _gradle(text, d, f, folder) -> Project:
    deps = re.findall(r"""(?:implementation|api|compile)\s*\(?\s*['"][^:'"]+:([^:'"]+)""", text)
    deps += re.findall(r"""project\(\s*['"]:([^'"]+)['"]""", text)
    return Project(d, folder, "java", f, deps, "application" in text or "org.springframework.boot" in text)


def _csproj(text, d, f, folder) -> Project:
    deps = re.findall(r'PackageReference\s+Include="([^"]+)"', text)
    runs = "Microsoft.NET.Sdk.Web" in text or re.search(r"<OutputType>\s*(Win)?Exe", text) is not None
    p = Project(d, PurePosixPath(f).stem, "csharp" if f.endswith(".csproj") else "fsharp", f, deps, runs)
    p.refs = [str(PurePosixPath(normalize(f"{d}/{r.replace(chr(92), '/')}")).parent) for r in
              re.findall(r'ProjectReference\s+Include="([^"]+)"', text)]   # resolved by the scanner
    return p


def _composer(text, d, f, folder) -> Project:
    j = json.loads(text)
    return Project(d, str(j.get("name") or folder), "php", f, [*j.get("require", {}), *j.get("require-dev", {})])


def _gemfile(text, d, f, folder) -> Project:
    return Project(d, folder, "ruby", f, re.findall(r"^\s*gem\s+['\"]([^'\"]+)", text, re.M))


READERS = {"package.json": _package_json, "pyproject.toml": _pyproject, "setup.py": _setup_py,
           "setup.cfg": lambda t, d, f, n: Project(d, (re.search(r"^name\s*=\s*(\S+)", t, re.M) or [None, n])[1],
                                                   "python", f),
           "requirements.txt": _requirements, "go.mod": _go_mod, "Cargo.toml": _cargo, "pom.xml": _pom,
           "composer.json": _composer, "Gemfile": _gemfile, "*.csproj": _csproj}
LANG = {"package.json": "javascript", "pyproject.toml": "python", "setup.py": "python", "setup.cfg": "python",
        "requirements.txt": "python", "go.mod": "go", "Cargo.toml": "rust", "pom.xml": "java",
        "build.gradle": "java", "build.gradle.kts": "java", "composer.json": "php", "Gemfile": "ruby", "*.csproj": "csharp"}
