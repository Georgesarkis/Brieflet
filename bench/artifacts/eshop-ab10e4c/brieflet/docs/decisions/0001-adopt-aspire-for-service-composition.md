# 0001. Adopt Aspire for Service Composition

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** infra-config
- **Confidence:** high

## Context

The team needs a unified way to compose and start all microservices. Aspire provides a single entry point for orchestration.

## Decision

The application host was updated to use Aspire's DistributedApplication. Redis, RabbitMQ, and Postgres are now added via builder extensions.

## Consequences

This centralizes infrastructure setup and simplifies local development. It may introduce dependency on Aspire's ecosystem and versioning.

## Evidence

Inferred by a local model from these commits and files:

- `dc7ea49` 2026-10-01 Update to Aspire 13.6.0 (#1039)
- `src/eShop.AppHost/AppHost.cs`

<!-- dev_docs key: aspire-orchestration -->
