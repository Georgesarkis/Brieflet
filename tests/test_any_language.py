"""brieflet init on repos that are not .NET Aspire: Python, TypeScript monorepo, a big monorepo, Go/Rust/.NET, folders only.
Offline: tiny repos written to a temp folder, fake model."""
import json
import subprocess
from pathlib import Path

from brieflet.bootstrap import brief_controller
from brieflet.domain.components import MAX_BOXES
from brieflet.infrastructure.git_snapshot import GitSnapshot
from brieflet.infrastructure.scanners import AllDecisions, FirstFound
from brieflet.infrastructure.dotnet.aspire_scanner import AspireScanner
from brieflet.infrastructure.dotnet.decision_scanner import DotnetDecisionScanner
from brieflet.infrastructure.generic.decision_scanner import GenericDecisionScanner
from brieflet.infrastructure.generic.workspace_scanner import WorkspaceScanner
from brieflet.presentation.views.ai_context_md import FILE as AI_CONTEXT
from brieflet.presentation.views.components_md import FILE as COMPONENTS

from .test_engine import FakeLLM

PY_COMPOSE = """services:
  api:
    build: ./api
    environment:
      DATABASE_URL: postgresql://app:${DB_PASSWORD}@db:5432/app
      REDIS_URL: redis://cache:6379/0
    depends_on: [db, cache]
  worker:
    build:
      context: .
      dockerfile: worker/Dockerfile
    depends_on:
      cache:
        condition: service_healthy
  db:
    image: postgres:16-alpine
  cache:
    image: redis:7
"""


def make_repo(tmp: Path, files: dict[str, str]) -> Path:
    r = tmp / "r"
    for path, txt in files.items():
        p = r / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
    for c in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", str(r), *c], check=True)
    return r


def scan(r: Path):
    s = GitSnapshot(r)
    g = FirstFound(AspireScanner(), WorkspaceScanner()).scan(s)
    return g, {c.key: c for c in AllDecisions(DotnetDecisionScanner(), GenericDecisionScanner()).scan(s, g)}


def by_name(g):
    return {c.name: c for c in g.components}


def arrows(g):
    return {(g.name_of(l.source), g.name_of(l.target)): l.label for l in g.links}


def python_repo(tmp):
    return make_repo(tmp, {
        "docker-compose.yml": PY_COMPOSE,
        "api/pyproject.toml": '[project]\nname = "shop-api"\ndependencies = ["fastapi>=0.110", "sqlalchemy", '
                              '"psycopg[binary]", "redis", "shop-common"]\n',
        "api/Dockerfile": "FROM python:3.12\n",
        "api/shop_api/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        "worker/pyproject.toml": '[project]\nname = "shop-worker"\ndependencies = ["celery[redis]", "shop_common"]\n',
        "worker/Dockerfile": "FROM python:3.12\n",
        "worker/tasks.py": "from celery import Celery\n",
        "common/pyproject.toml": '[project]\nname = "shop-common"\ndependencies = ["pydantic"]\n',
        "common/shop_common/__init__.py": "",
        "docs/requirements.txt": "mkdocs\n",
        ".github/workflows/ci.yml": "on: push\n",
    })


def test_python_repo_with_compose(tmp_path):
    g, dec = scan(python_repo(tmp_path))
    names = by_name(g)
    assert set(names) == {"api", "worker", "db", "cache", "shop-common"}
    assert names["api"].path == "api" and names["api"].tech == "Python" and names["api"].kind == "service"
    assert names["worker"].path == "worker"                      # context . + worker/Dockerfile
    assert names["db"].tech == "PostgreSQL" and names["db"].is_storage and names["cache"].tech == "Redis"
    assert names["shop-common"].kind == "library"
    a = arrows(g)
    assert a[("api", "db")] == "db" and a[("api", "cache")] == "cache" and ("worker", "cache") in a
    assert ("api", "shop-common") in a and ("worker", "shop-common") in a       # shop_common == shop-common
    assert g.project_refs[names["api"].id] == ["shop-common"]
    assert {"docker-compose", "ci", "sql-database", "redis", "background-jobs", "web-framework"} <= set(dec)
    assert "PostgreSQL" in dec["sql-database"].reason and "api/pyproject.toml" in dec["sql-database"].evidence
    assert "fastapi" in dec["web-framework"].excerpt


def ts_repo(tmp):
    pj = lambda **k: json.dumps(k)
    return make_repo(tmp, {
        "package.json": pj(name="acme", private=True, workspaces=["apps/*", "packages/*"]),
        "pnpm-workspace.yaml": "packages:\n  - apps/*\n  - packages/*\n",
        "turbo.json": "{}",
        "apps/web/package.json": pj(name="@acme/web", scripts={"dev": "next dev", "start": "next start"},
                                    dependencies={"next": "15", "react": "19", "@acme/ui": "workspace:*"},
                                    devDependencies={"@acme/tsconfig": "workspace:*", "@types/react": "19"}),
        "apps/web/tsconfig.json": "{}",
        "apps/web/app/page.tsx": "export default function Page() { return null }\n",
        "apps/api/package.json": pj(name="@acme/api", main="dist/server.js",
                                    dependencies={"express": "4", "ioredis": "5", "@acme/db": "workspace:*"}),
        "apps/api/tsconfig.json": "{}",
        "apps/api/Dockerfile": "FROM node:22\n",
        "apps/api/src/server.ts": "import express from 'express'\n",
        "packages/ui/package.json": pj(name="@acme/ui", dependencies={"react": "19"}, devDependencies={"vite": "5"}),
        "packages/ui/tsconfig.json": "{}",
        "packages/ui/src/button.tsx": "export const Button = () => null\n",
        "packages/db/package.json": pj(name="@acme/db", dependencies={"@prisma/client": "5", "pg": "8"}),
        "packages/db/prisma/schema.prisma": "datasource db { provider = \"postgresql\" }\n",
        "packages/tsconfig/package.json": pj(name="@acme/tsconfig"),
        "examples/demo/package.json": pj(name="demo", dependencies={"express": "4"}),
        "node_modules/left-pad/package.json": pj(name="left-pad"),
    })


def test_typescript_monorepo(tmp_path):
    g, dec = scan(ts_repo(tmp_path))
    names = by_name(g)
    assert set(names) == {"@acme/web", "@acme/api", "@acme/ui", "@acme/db", "@acme/tsconfig", "redis", "postgresql"}
    assert "acme" not in names and "demo" not in names and "left-pad" not in names   # root, examples, node_modules
    assert names["@acme/web"].kind == "service" and names["@acme/web"].tech == "TypeScript"
    assert names["@acme/api"].kind == "service" and names["@acme/api"].entry is None
    assert names["@acme/ui"].kind == "library"        # vite only in devDependencies: still a library
    a = arrows(g)
    assert ("@acme/web", "@acme/ui") in a and ("@acme/web", "@acme/tsconfig") in a
    assert a[("@acme/api", "redis")] == "cache" and a[("@acme/db", "postgresql")] == "db"
    assert {"monorepo", "sql-database", "redis", "web-framework"} <= set(dec)
    assert set(dec["monorepo"].evidence) == {"pnpm-workspace.yaml", "turbo.json", "package.json"}
    assert "through an ORM" in dec["sql-database"].reason
    assert all("examples/" not in e for c in dec.values() for e in c.evidence)


def test_big_monorepo_is_cut_to_max_boxes(tmp_path):
    files = {"package.json": json.dumps({"name": "big", "workspaces": ["apps/*", "packages/*", "tools/*"]})}
    for i in range(80):
        deps = {"@big/core": "*"} if i else {}
        files[f"packages/p{i:02d}/package.json"] = json.dumps({"name": f"@big/{'core' if i == 0 else f'p{i:02d}'}",
                                                               "dependencies": deps})
    for i in range(25):
        files[f"tools/t{i:02d}/package.json"] = json.dumps({"name": f"@big/t{i:02d}"})
    for app in ("web", "admin", "api"):
        files[f"apps/{app}/package.json"] = json.dumps({"name": f"@big/{app}", "scripts": {"start": "node ."},
                                                        "dependencies": {"@big/core": "*", "@big/p01": "*"}})
    g, _ = scan(make_repo(tmp_path, files))
    names = by_name(g)
    assert len(g.components) <= MAX_BOXES
    assert {"@big/web", "@big/admin", "@big/api", "@big/core"} <= set(names)    # apps + most used library stay
    assert {"packages/*", "tools/*"} <= set(names) and names["packages/*"].kind == "group"
    assert names["tools/*"].tech == "25 packages"
    assert ("@big/web", "@big/core") in arrows(g)
    assert any("grouped by folder" in n for n in g.notes)
    for l in g.links:
        assert l.source != l.target



def test_big_monorepo_keeps_big_undeclared_package_and_drops_noise(tmp_path):
    """cal.com shape: the biggest package is imported by path (few declared users), compose adds a whole-repo
    service and dev-tool containers, and a tiny package looks like a service."""
    files = {"package.json": json.dumps({"name": "big", "workspaces": ["apps/*", "packages/*"]}),
             "Dockerfile": "FROM node\n",
             "docker-compose.yml": "services:\n  db:\n    image: postgres\n  app:\n    build: .\n    depends_on: [db]\n"
                                   "  mail:\n    image: mailhog/mailhog\n  studio:\n    image: some/studio\n"}
    for i in range(40):
        files[f"packages/p{i:02d}/package.json"] = json.dumps({"name": f"@big/p{i:02d}", "dependencies": {"@big/lib": "*"}})
    files["packages/lib/package.json"] = json.dumps({"name": "@big/lib"})
    files["packages/features/package.json"] = json.dumps({"name": "@big/features"})
    for i in range(300):
        files[f"packages/features/f{i}.ts"] = "export const x = 1;\n"
    files["packages/tiny/package.json"] = json.dumps({"name": "@big/tiny", "dependencies": {"next": "15"}})
    files["apps/web/package.json"] = json.dumps({"name": "@big/web", "dependencies": {"next": "15", "@big/lib": "*"}})
    for i in range(20):
        files[f"apps/web/page{i}.tsx"] = "export default 1;\n"
    g, _ = scan(make_repo(tmp_path, files))
    names = by_name(g)
    assert len(g.components) <= MAX_BOXES
    assert {"@big/web", "@big/lib", "@big/features"} <= set(names)
    assert not {"app", "mail", "studio"} & set(names)       # whole-repo service + unused dev containers dropped
    assert "@big/tiny" not in names                         # 0 code files: no service bonus

def test_go_rust_dotnet_projects(tmp_path):
    g, dec = scan(make_repo(tmp_path, {
        "svc/go.mod": "module github.com/acme/svc\n\ngo 1.22\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n"
                      "\tgithub.com/redis/go-redis/v9 v9.5.1\n)\n",
        "svc/main.go": "package main\n",
        "cli/Cargo.toml": '[package]\nname = "acme-cli"\n\n[dependencies]\nclap = "4"\n',
        "cli/src/main.rs": "fn main() {}\n",
        "Directory.Build.props": "<Project/>",
        "src/Web/Web.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"><ItemGroup>'
                              '<ProjectReference Include="..\\Core\\Core.csproj" /></ItemGroup></Project>',
        "src/Core/Core.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>',
        "api.proto": 'syntax = "proto3";\n',
    }))
    names = by_name(g)
    assert names["github.com/acme/svc"].kind == "service" and names["github.com/acme/svc"].tech == "Go"
    assert names["acme-cli"].kind == "service" and names["acme-cli"].entry == "cli/src/main.rs"
    assert names["Web"].kind == "service" and names["Core"].kind == "library" and names["Web"].tech == "C#"
    a = arrows(g)
    assert ("Web", "Core") in a and a[("github.com/acme/svc", "redis")] == "cache"
    assert "grpc" in dec and "web-framework" in dec


def test_folders_only_repo(tmp_path):
    g, _ = scan(make_repo(tmp_path, {"src/parser/a.c": "", "src/parser/b.c": "", "src/net/c.c": "", "README.md": ""}))
    assert {(c.name, c.path, c.kind) for c in g.components} == {("parser", "src/parser", "module"),
                                                                ("net", "src/net", "module")}
    assert "top code folders" in g.origin


def test_init_on_typescript_repo_writes_docs(tmp_path):
    r = ts_repo(tmp_path)
    out = tmp_path / "out"
    job = brief_controller(r, FakeLLM(), out, log=lambda *a: None)
    plan = job.plan()
    assert len(plan.graph.components) == 7 and plan.candidates
    job.run(plan)
    comp = (out / COMPONENTS).read_text()
    assert "package manifests" in comp and "@acme/web" in comp and "None" not in comp
    ctx = (out / AI_CONTEXT).read_text()
    assert "`apps/web`" in ctx and "TypeScript" not in ctx.split("## Components")[0]


def test_init_on_python_repo_writes_docs(tmp_path):
    r = python_repo(tmp_path)
    out = tmp_path / "out"
    job = brief_controller(r, FakeLLM(), out, log=lambda *a: None)
    res = job.run(job.plan())
    comp = (out / COMPONENTS).read_text()
    assert "Docker Compose" in comp and 'db[("db<br/>' in comp and "api -->|db| db" in comp
    assert any(f.startswith("docs/decisions/") for f in res.files)
