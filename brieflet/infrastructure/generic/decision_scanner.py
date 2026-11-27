"""DecisionScanner for any language: decisions shown by files (compose, Kubernetes, Terraform, CI, .proto, monorepo
tools) and by dependencies in the package manifests (frameworks, databases, message buses, auth, background jobs).

Reads only manifests (already read by the component scan) and file names, so it stays fast on repos with 10k+ files.
Skipped for .NET Aspire repos: there the .NET scanner's signals are used, unchanged.
"""
from __future__ import annotations

import re

from ...domain.components import ComponentGraph
from ...domain.decisions import DecisionCandidate
from .compose import compose_files
from .manifests import RUNNERS, main_part, read_projects, skipped
from .tech import INFRA, client_tech

# key, type, reason, file-name regex (matched on the whole path)
FILE_SIGNALS = [
    ("docker-compose", "infra-config", "the system runs as containers started with Docker Compose", None),
    ("kubernetes", "infra-config", "it is deployed to Kubernetes (manifests or Helm charts)",
     r"(^|/)(Chart\.yaml|kustomization\.ya?ml)$|(^|/)(k8s|kubernetes|helm|charts|manifests)/.*\.ya?ml$"),
    ("terraform", "infra-config", "cloud infrastructure is written as code (Terraform)", r"\.tf$"),
    ("monorepo", "infra-config", "many packages live in one repository, managed by a monorepo tool",
     r"^(pnpm-workspace\.yaml|nx\.json|turbo\.json|lerna\.json|rush\.json|go\.work)$"),
    ("grpc", "communication", "services define their APIs in Protocol Buffers and call each other over gRPC", r"\.proto$"),
    ("graphql", "communication", "clients query the backend through a GraphQL API", r"\.(graphql|gql)$"),
    ("ci", "infra-config", "every change is built and tested by a CI pipeline",
     r"^(\.github/workflows/.+\.ya?ml|\.gitlab-ci\.yml|azure-pipelines\.ya?ml|Jenkinsfile|\.circleci/config\.yml)$"),
]
ORMS = {"prisma", "@prisma/client", "typeorm", "sequelize", "drizzle-orm", "knex", "mikro-orm", "sqlalchemy", "sqlmodel",
        "django", "peewee", "tortoise-orm", "alembic", "gorm.io/gorm", "diesel", "sqlx", "sea-orm",
        "spring-boot-starter-data-jpa", "hibernate-core", "microsoft.entityframeworkcore", "dapper"}
AUTH = {"next-auth", "@auth/core", "passport", "jsonwebtoken", "jose", "pyjwt", "python-jose", "authlib", "django-allauth",
        "keycloak-js", "@clerk/nextjs", "firebase-admin", "spring-boot-starter-security", "oauthlib", "golang-jwt/jwt",
        "jsonwebtoken-rs", "microsoft.aspnetcore.authentication.jwtbearer"}
JOBS = {"celery", "rq", "dramatiq", "arq", "bullmq", "bull", "agenda", "sidekiq", "hangfire", "temporalio",
        "@temporalio/client", "asynq", "quartz"}
GRAPHQL = {"graphql", "@apollo/server", "apollo-server", "@apollo/client", "graphql-yoga", "strawberry-graphql",
           "graphene", "ariadne", "gqlgen", "async-graphql", "urql"}
GRPC = {"@grpc/grpc-js", "grpcio", "google.golang.org/grpc", "tonic", "grpc.aspnetcore", "nice-grpc"}


def _dep_signals(deps: set[str]) -> list[tuple[str, str, str, set[str]]]:
    """(key, type, reason, matching dependency names) for the dependencies a repo has."""
    techs: dict[str, set[str]] = {}
    for d in deps:
        if t := client_tech(d):
            techs.setdefault(t, set()).add(d)

    def kind(*kinds: str) -> set[str]:
        return {t for t in techs if INFRA[t][0] in kinds}

    out = []
    if q := kind("queue"):
        out.append(("message-bus", "communication", f"services exchange messages over {', '.join(sorted(q))}",
                    {d for t in q for d in techs[t]}))
    if "Redis" in techs:
        out.append(("redis", "storage", "data is kept in Redis (cache, sessions or queues)", techs["Redis"]))
    sql = {t for t in kind("database") if t in ("PostgreSQL", "MySQL", "MariaDB", "SQL Server", "SQLite")}
    orm = {d for d in deps if d.lower() in ORMS or d.lower().endswith(tuple("/" + o for o in ORMS if "/" in o))
           or d.lower().startswith("microsoft.entityframeworkcore")}
    if sql or orm:
        what = ", ".join(sorted(sql)) or "a SQL database"
        out.append(("sql-database", "storage", f"data is stored in {what}" + (" through an ORM" if orm else ""),
                    orm | {d for t in sql for d in techs[t]}))
    if docs := kind("database") - sql:
        out.append(("document-store", "storage", f"data is stored in {', '.join(sorted(docs))}",
                    {d for t in docs for d in techs[t]}))
    for key, typ, reason, names in (
            ("web-framework", "framework", "the apps and APIs are built on {}", RUNNERS),
            ("auth", "auth", "users and services authenticate with tokens ({})", AUTH),
            ("background-jobs", "new-pattern", "slow work runs in background jobs ({})", JOBS),
            ("graphql", "communication", "clients query the backend through GraphQL ({})", GRAPHQL),
            ("grpc", "communication", "services call each other over gRPC ({})", GRPC)):
        hit = {d for d in deps if d.lower() in names or any(d.lower().endswith("/" + n) for n in names if "/" in n)}
        if hit:
            out.append((key, typ, reason.format(", ".join(sorted(hit)[:4])), hit))
    return out


class GenericDecisionScanner:
    def scan(self, snapshot, graph: ComponentGraph) -> list[DecisionCandidate]:
        if graph.apphost:
            return []
        projects = main_part(read_projects(snapshot), lambda p: p.manifest)
        out: list[DecisionCandidate] = []
        files = main_part([f for f in snapshot.files if not skipped(f)])
        for key, typ, reason, rx in FILE_SIGNALS:
            hits = compose_files(snapshot) if rx is None else [f for f in files if re.search(rx, f)]
            if key == "monorepo":
                hits += [p.manifest for p in projects if p.workspace_root]
            if hits:
                out.append(self._candidate(snapshot, key, typ, reason, hits[:6], None))
        deps = {d for p in projects for d in p.deps}
        for key, typ, reason, names in _dep_signals(deps):
            evidence = [p.manifest for p in projects if names & set(p.deps)][:6]
            found = next((c for c in out if c.key == key), None)
            if found:   # file + dependency evidence for the same decision (e.g. .proto files and grpcio)
                found.evidence = list(dict.fromkeys([*found.evidence, *evidence]))[:6]
            elif evidence:
                out.append(self._candidate(snapshot, key, typ, reason, evidence, names))
        return out

    @staticmethod
    def _candidate(snapshot, key, typ, reason, evidence, names) -> DecisionCandidate:
        commits = list(dict.fromkeys(c for f in evidence[:3] if (c := snapshot.commit_that_added(f))))
        return DecisionCandidate(key, typ, reason, evidence, _excerpt(snapshot, evidence, names), commits)


def _excerpt(snapshot, evidence: list[str], names: set[str] | None) -> str:
    out = ""
    for f in evidence[:3]:
        lines = (snapshot.read(f) or "").splitlines()
        if names:
            hit = [l.strip() for l in lines if any(n in l for n in names)][:8]
        else:
            hit = lines[:12]
        if hit:
            out += f"--- {f}\n" + "\n".join(hit) + "\n"
    return out
