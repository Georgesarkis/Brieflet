# 0010. Add Webhook Registration Service

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** communication
- **Confidence:** medium

## Context

External systems need to receive events via webhooks. The Identity API configuration lists a webhooks resource. A dedicated service is required to handle webhook registration and delivery.

## Decision

A new WebhookClient service is created to manage webhook endpoints. It registers routes for webhook registration and authentication. The Identity API references this service as a resource.

## Consequences

External systems can now receive events reliably. This adds complexity to the deployment pipeline and requires managing webhook tokens.

## Evidence

Inferred by a local model from these commits and files:

- `fc61f90` 2023-10-30 Initial commit of eShop.
- `9fe8785` 2023-11-13 Reorganize WebhookClient to match the updated file layout conventions (#71)
- `src/Identity.API/Configuration/Config.cs`
- `src/WebhookClient/Endpoints/AuthenticationEndpoints.cs`
- `src/WebhookClient/Endpoints/WebhookEndpoints.cs`
- `src/WebhookClient/Extensions/Extensions.cs`

<!-- dev_docs key: webhooks -->
