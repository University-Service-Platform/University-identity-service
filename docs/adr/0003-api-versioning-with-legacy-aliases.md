# ADR 0003: Version the API under /api/v1 and keep Sprint 1 routes as deprecated aliases

**Status:** Accepted · **Date:** 2026-09-26

## Context
Sprint 1 exposed unversioned routes (`/users`, `/validation/users/{id}`, …) that other teams may already call. The project rules require communicating breaking API changes before implementation, and the final API Gateway base path has not been confirmed.

## Decision
- Expose every API route under **`/api/v1`**; `/health` and `/.well-known/jwks.json` stay at the root.
- Keep the Sprint 1 routes working unchanged as **deprecated aliases**: marked deprecated in OpenAPI, and responding with `Deprecation: true` and a `Link` header naming the successor.
- New security behavior applies only to the v1 routes: `/api/v1/validation/users/{id}` requires a token and omits email.
- The gateway path is kept out of the service; a suggested route is documented for the Gateway team to confirm.

## Consequences
- No existing consumer breaks; migration can happen on each team's schedule.
- Two routes exist temporarily for Sprint 1 operations. A test ensures every legacy operation is flagged as deprecated, and removal will be announced.
