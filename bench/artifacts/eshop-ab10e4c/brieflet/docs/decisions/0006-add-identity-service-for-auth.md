# 0006. Add Identity service for auth

- **Status:** Inferred — needs human confirm
- **Date:** 2026-11-22
- **Type:** auth
- **Confidence:** high

## Context

The eShop project requires secure authentication for its applications and APIs. A separate Identity service is needed to issue OpenID Connect tokens.

## Decision

A dedicated Identity service will be created to handle authentication. It will issue OpenID Connect tokens to the WebApp and WebhookClient services.

## Consequences

This centralizes authentication logic and improves security. It adds complexity to the deployment pipeline and requires token validation in consuming services.

## Evidence

Inferred by a local model from these commits and files:

- `fc61f90` 2023-10-30 Initial commit of eShop.
- `Directory.Packages.props`
- `src/Identity.API/GlobalUsings.cs`
- `src/Identity.API/Identity.API.csproj`
- `src/Identity.API/Program.cs`
- `src/WebApp/Extensions/Extensions.cs`
- `src/WebhookClient/Extensions/Extensions.cs`

<!-- dev_docs key: identity-server -->
