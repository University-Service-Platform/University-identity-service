# ADR 0002: Read organizational data from the Directory Service API, never duplicate it

**Status:** Accepted · **Date:** 2026-09-26

## Context
Group 5 owns two services. The University Directory Service already owns faculties, departments, service units, user affiliations and service responsibilities. The Identity Service needs that data for profiles and for the key business rule that authorization must consider both system role and department or service responsibility. The case specification requires preserving service data ownership and avoiding a shared database.

## Decision
The Identity Service stores **only** identity data (users, roles, permissions, status, audit). It reads affiliations and responsibilities through a dedicated HTTP client (`app/integrations/directory_client.py`) that calls the Directory Service's documented endpoints, configured by `DIRECTORY_SERVICE_BASE_URL`. Responsibility-aware decisions are exposed to other teams as one eligibility endpoint.

## Consequences
- There is a single source of truth per entity, and no synchronization or drift.
- The Identity Service depends on Directory availability for relationship checks. Mitigations:
  - Identity checks run first, so an inactive or wrong-role user is rejected without calling the Directory.
  - Timeouts are short.
  - Failures return `503 DEPENDENCY_UNAVAILABLE` rather than a guessed answer.
  - Profiles degrade gracefully to `affiliation_status: UNAVAILABLE`.
- Changes to the Directory contract are caught by the client's contract tests.
