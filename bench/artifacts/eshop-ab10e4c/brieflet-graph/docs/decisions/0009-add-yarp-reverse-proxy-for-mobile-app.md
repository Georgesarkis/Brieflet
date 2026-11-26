# 0009. Add YARP reverse proxy for mobile app

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** communication
- **Confidence:** medium

## Context

The mobile app needs a backend-for-frontend to handle API routing and authentication. A YARP reverse proxy was chosen to centralize this communication layer.

## Decision

A YARP reverse proxy is configured as the backend-for-frontend for the mobile app. The AppHost.cs file is updated to include Redis, RabbitMQ, and PostgreSQL services.

## Consequences

This setup centralizes mobile app communication and simplifies routing. It may introduce additional latency and complexity in the proxy layer.

## Evidence

Inferred by a local model from these commits and files:

- `dc7ea49` 2026-10-01 Update to Aspire 13.6.0 (#1039)
- `src/eShop.AppHost/AppHost.cs`

<!-- dev_docs key: yarp-mobile-bff -->
