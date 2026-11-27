"""Docker Compose files → services (name, image, build folder, depends_on, the hosts its settings point at)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .manifests import normalize, side, skipped

COMPOSE_RE = re.compile(r"^(docker-)?compose(\.[\w-]+)?\.ya?ml$")
URL_HOST_RE = re.compile(r"(?:(\w+)://)?(?:[^@/\s:\"']+(?::[^@/\s\"']*)?@)?([a-z][a-z0-9_-]*)(?::\d+)")


@dataclass
class ComposeService:
    name: str
    file: str
    image: str = ""
    build: str | None = None                  # repo folder of the build context
    depends_on: list[str] = field(default_factory=list)
    calls: dict[str, str] = field(default_factory=dict)   # host (another service) → protocol ("HTTP", "") from env
    side: bool = False                        # built from a second Dockerfile (Dockerfile.playwright): a helper container


def compose_files(snapshot) -> list[str]:
    """Main compose files first (root, then shortest path); overrides / test files last."""
    hits = [f for f in snapshot.files if COMPOSE_RE.match(PurePosixPath(f).name) and not skipped(f) and not side(f)]
    return sorted(hits, key=lambda f: ("test" in f.lower(), "." in PurePosixPath(f).stem.replace("docker-compose", ""),
                                       f.count("/"), f))


def read_services(snapshot, notes: list[str]) -> list[ComposeService]:
    files = compose_files(snapshot)
    if not files:
        return []
    try:
        import yaml
    except ImportError:
        notes.append("compose files skipped: pip install pyyaml to read them")
        return []
    out: dict[str, ComposeService] = {}
    for f in files[:6]:
        try:
            doc = yaml.safe_load(snapshot.read(f) or "") or {}
        except yaml.YAMLError:
            notes.append(f"compose file not readable: {f}")
            continue
        services = doc.get("services") if isinstance(doc, dict) else None
        for name, spec in (services or {}).items():
            if isinstance(spec, dict):
                _merge(out, _service(str(name), f, spec))
    names = set(out)
    for s in out.values():
        s.depends_on = [d for d in s.depends_on if d in names and d != s.name]
        s.calls = {h: p for h, p in s.calls.items() if h in names and h != s.name}
    return list(out.values())


def _merge(out: dict[str, ComposeService], s: ComposeService) -> None:
    """Override files (compose.override.yml, …) add what the main file left out, like `docker compose` does."""
    old = out.setdefault(s.name, s)
    if old is not s:
        old.image = old.image or s.image
        if old.build is None:
            old.build, old.side = s.build, s.side
        old.depends_on += [d for d in s.depends_on if d not in old.depends_on]
        for h, proto in s.calls.items():
            old.calls.setdefault(h, proto)


def _service(name: str, file: str, spec: dict) -> ComposeService:
    base = str(PurePosixPath(file).parent) if "/" in file else ""
    build = spec.get("build")
    ctx = (build.get("context") or ".") if isinstance(build, dict) else build
    folder = _join(base, ctx) if isinstance(ctx, str) else None
    dockerfile = build.get("dockerfile") if isinstance(build, dict) else None
    if folder is not None and isinstance(dockerfile, str) and "/" in dockerfile:   # context . + backend/Dockerfile
        folder = _join(folder, str(PurePosixPath(dockerfile).parent))
    s = ComposeService(name, file, str(spec.get("image") or ""), folder)
    s.side = isinstance(dockerfile, str) and PurePosixPath(dockerfile).name != "Dockerfile"
    deps = spec.get("depends_on") or []
    s.depends_on = [str(d) for d in (deps if isinstance(deps, list) else deps.keys() if isinstance(deps, dict) else [])]
    env = spec.get("environment") or {}
    values = env.values() if isinstance(env, dict) else [str(e).split("=", 1)[-1] for e in env if isinstance(e, str)]
    for v in values:
        for scheme, host in URL_HOST_RE.findall(str(v or "")):
            s.calls.setdefault(host, "HTTP" if scheme.startswith("http") else "gRPC" if scheme == "grpc" else "")
    return s


def _join(base: str, rel: str) -> str:
    return normalize(f"{base}/{rel.strip()}")
