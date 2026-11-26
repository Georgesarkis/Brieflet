# 0005. Use Redis for basket storage

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** storage
- **Confidence:** medium

## Context

The basket API needs a fast, distributed storage solution for shopping carts. Redis was chosen for its low latency and in-memory performance. The AppHost configuration now includes Redis alongside RabbitMQ and Postgres.

## Decision

Redis is integrated into the application via AddRedis in the AppHost configuration. The basket service uses Redis to store and retrieve cart data. Functional tests verify Redis connectivity and basket operations.

## Consequences

Redis provides fast read/write performance for basket operations. This choice increases infrastructure complexity and requires Redis cluster management. Data persistence depends on Redis configuration settings.

## Evidence

Inferred by a local model from these commits and files:

- `fc61f90` 2023-10-30 Initial commit of eShop.
- `dc7ea49` 2026-10-01 Update to Aspire 13.6.0 (#1039)
- `ae71a06` 2026-08-18 Upgrade Aspire and .NET 10 (#1008)
- `src/Basket.API/Extensions/Extensions.cs`
- `src/eShop.AppHost/AppHost.cs`
- `tests/Basket.FunctionalTests/RedisFixture.cs`
- `tests/eShop.AppHost.UnitTests/AppHostConfigurationTests.cs`

<!-- dev_docs key: redis-basket -->
