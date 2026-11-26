# 0008. Implement CQRS with MediatR for Ordering

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** new-pattern
- **Confidence:** high

## Context

The ordering service requires a clear separation between commands and queries. The team decided to adopt CQRS to handle this separation.

## Decision

The team implemented CQRS using MediatR. Commands are handled by dedicated handlers that modify state. Queries are handled by separate handlers that return data.

## Consequences

This separation improves testability and maintainability. It also adds complexity to the codebase.

## Evidence

Inferred by a local model from these commits and files:

- `fc61f90` 2023-10-30 Initial commit of eShop.
- `src/Ordering.API/Application/Commands/CancelOrderCommandHandler.cs`
- `src/Ordering.API/Application/Commands/CreateOrderCommandHandler.cs`
- `src/Ordering.API/Application/Commands/CreateOrderDraftCommandHandler.cs`
- `src/Ordering.API/Application/Commands/IdentifiedCommandHandler.cs`
- `src/Ordering.API/Application/Commands/SetAwaitingValidationOrderStatusCommandHandler.cs`
- `src/Ordering.API/Application/Commands/SetPaidOrderStatusCommandHandler.cs`

<!-- dev_docs key: cqrs-mediatr-ordering -->
