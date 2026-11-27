"""DecisionScanner for .NET: finds evidence of known architecture decisions in C# code + the commits that added it."""
from __future__ import annotations

import re

from ...domain.components import ComponentGraph
from ...domain.decisions import DecisionCandidate, DecisionSignal

SIGNALS = [
    DecisionSignal("aspire-orchestration", "infra-config", "the whole system is composed and started by a .NET Aspire AppHost", None),
    DecisionSignal("rabbitmq-event-bus", "communication", "services publish/subscribe integration events over RabbitMQ",
                   r"AddRabbitMQ\(|AddRabbitMqEventBus\("),
    DecisionSignal("grpc", "communication", "some services are called over gRPC", r"MapGrpcService<|AddGrpcClient<"),
    DecisionSignal("postgresql-storage", "storage", "services store data in PostgreSQL", r"AddPostgres\(|AddNpgsqlDbContext<"),
    DecisionSignal("redis", "storage", "data is kept in Redis", r"AddRedis(Client)?\("),
    DecisionSignal("identity-service", "auth", "a separate identity service issues tokens (OpenID Connect) for the apps and APIs",
                   r"AddIdentityServer|Duende|AddOpenIdConnect|AddJwtBearer"),
    DecisionSignal("outbox-integration-event-log", "new-pattern",
                   "integration events are saved with the data change (outbox) before publishing", r"IntegrationEventLog"),
    DecisionSignal("cqrs-mediatr", "new-pattern", "commands/queries go through MediatR (CQRS)", r"IRequestHandler<|AddMediatR"),
    DecisionSignal("yarp-bff", "communication", "a YARP reverse proxy is a backend-for-frontend", r"AddYarp\("),
    DecisionSignal("webhooks", "communication", "external systems get events through registered webhooks", r"Webhook"),
]
CODE_FILES = (".cs", ".csproj", ".props")
EXCERPT_HIT = re.compile(r"Add\w+|Map\w+|IntegrationEvent|IRequestHandler|Webhook")


class DotnetDecisionScanner:
    def scan(self, snapshot, graph: ComponentGraph) -> list[DecisionCandidate]:
        code = [f for f in snapshot.files if f.endswith(CODE_FILES)]
        out = []
        for s in SIGNALS:
            evidence = self._evidence(snapshot, graph, code, s)
            if evidence:
                out.append(DecisionCandidate(s.key, s.type, s.reason, evidence, self._excerpt(snapshot, evidence),
                                             self._commits(snapshot, evidence)))
        return out

    @staticmethod
    def _evidence(snapshot, graph: ComponentGraph, code: list[str], s: DecisionSignal) -> list[str]:
        if s.pattern is None:
            return [f"{graph.apphost}/{x}" for x in ("AppHost.cs", "Program.cs") if snapshot.has(f"{graph.apphost}/{x}")]
        rx = re.compile(s.pattern)
        return [f for f in code if rx.search(snapshot.read(f) or "")][:6]

    @staticmethod
    def _commits(snapshot, evidence: list[str]) -> list[str]:
        found = [snapshot.commit_that_added(f) for f in evidence[:3]]
        return list(dict.fromkeys(c for c in found if c))

    @staticmethod
    def _excerpt(snapshot, evidence: list[str]) -> str:
        out = ""
        for f in evidence[:3]:
            lines = (snapshot.read(f) or "").splitlines()
            hit = next((i for i, l in enumerate(lines) if EXCERPT_HIT.search(l)), None)
            if hit is not None:
                out += f"--- {f}\n" + "\n".join(lines[max(0, hit - 2): hit + 8]) + "\n"
        return out
