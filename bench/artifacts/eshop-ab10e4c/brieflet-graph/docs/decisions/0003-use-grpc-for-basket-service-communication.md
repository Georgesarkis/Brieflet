# 0003. Use gRPC for basket service communication

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** communication
- **Confidence:** medium

## Context

The basket service needs to communicate with other services. The team chose gRPC for this communication.

## Decision

The basket service is configured to use gRPC. The WebApp is extended to support gRPC.

## Consequences

gRPC provides efficient communication. It may increase complexity in the system.

## Evidence

Inferred by a local model from these commits and files:

- `fc61f90` 2023-10-30 Initial commit of eShop.
- `src/Basket.API/Program.cs`
- `src/WebApp/Extensions/Extensions.cs`

<!-- dev_docs key: grpc-basket -->
