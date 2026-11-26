# 0002. Use RabbitMQ for inter-service communication

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** communication
- **Confidence:** medium

## Context

The eShop microservices require a reliable way to share integration events. The team chose RabbitMQ to decouple services and enable asynchronous communication.

## Decision

Services publish and subscribe to integration events via RabbitMQ. The EventBusRabbitMQ package handles connection and message routing. OpenTelemetry is added for observability.

## Consequences

This approach improves scalability and resilience. It introduces operational complexity and message ordering challenges.

## Evidence

Inferred by a local model from these commits and files:

- `fc61f90` 2023-10-30 Initial commit of eShop.
- `src/Basket.API/Extensions/Extensions.cs`
- `src/Catalog.API/Extensions/Extensions.cs`
- `src/EventBusRabbitMQ/RabbitMqDependencyInjectionExtensions.cs`
- `src/OrderProcessor/Extensions/Extensions.cs`
- `src/Ordering.API/Extensions/Extensions.cs`
- `src/PaymentProcessor/Program.cs`

<!-- dev_docs key: rabbitmq-event-bus -->
