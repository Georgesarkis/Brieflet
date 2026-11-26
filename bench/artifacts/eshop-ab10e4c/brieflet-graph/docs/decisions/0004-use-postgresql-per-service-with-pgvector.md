# 0004. Use PostgreSQL per service with pgvector

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** storage
- **Confidence:** medium

## Context

The eShop microservices repository requires a persistent data store for each service. The team chose PostgreSQL as the database engine and enabled pgvector for vector search capabilities.

## Decision

Each service will use its own dedicated PostgreSQL database. The Catalog, Identity, and Webhooks services are configured with separate database contexts and connection strings. pgvector is used to support vector operations within the Catalog service.

## Consequences

This approach ensures data isolation and simplifies deployment. It increases infrastructure complexity and operational overhead for managing multiple database instances.

## Evidence

Inferred by a local model from these commits and files:

- `fc61f90` 2023-10-30 Initial commit of eShop.
- `src/Catalog.API/Extensions/Extensions.cs`
- `src/Identity.API/Program.cs`
- `src/Webhooks.API/Extensions/Extensions.cs`
- `src/eShop.AppHost/AppHost.cs`
- `tests/Catalog.FunctionalTests/CatalogApiFixture.cs`
- `tests/Ordering.FunctionalTests/OrderingApiFixture.cs`

<!-- dev_docs key: postgresql-storage -->
