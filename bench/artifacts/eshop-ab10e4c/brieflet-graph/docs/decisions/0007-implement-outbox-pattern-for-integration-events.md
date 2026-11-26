# 0007. Implement outbox pattern for integration events

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** new-pattern
- **Confidence:** medium

## Context

The repository introduces a new pattern where integration events are persisted alongside data changes. This approach ensures reliable event delivery by storing events in an outbox table before publishing them.

## Decision

The team decided to use the outbox pattern to handle integration events. Events are saved to the database within the same transaction as the data change, ensuring consistency and preventing message loss.

## Consequences

This approach improves reliability by preventing message loss during failures. However, it adds complexity to the architecture and requires additional infrastructure for event processing.

## Evidence

Inferred by a local model from these commits and files:

- `fc61f90` 2023-10-30 Initial commit of eShop.
- `src/Catalog.API/Apis/CatalogApi.cs`
- `src/Catalog.API/Catalog.API.csproj`
- `src/Catalog.API/Extensions/Extensions.cs`
- `src/Catalog.API/GlobalUsings.cs`
- `src/Catalog.API/Infrastructure/CatalogContext.cs`
- `src/Catalog.API/Infrastructure/Migrations/20231026091140_Outbox.Designer.cs`

<!-- dev_docs key: outbox-integration-event-log -->
