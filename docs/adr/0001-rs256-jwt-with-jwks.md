# ADR 0001: Sign access tokens with RS256 and publish a JWKS

**Status:** Accepted · **Date:** 2026-09-26

## Context
The Identity Service issues JWTs that the API Gateway and the services of Groups 6, 7 and 8 must verify. With HS256, every verifier needs the same shared secret, and any service holding that secret could also mint tokens for any user.

## Decision
Sign tokens with **RS256**. The Identity Service alone holds the private key and publishes the public key at `/.well-known/jwks.json` (with a `kid` equal to the RFC 7638 thumbprint). Tokens carry `sub`, `university_id`, `account_type`, `roles`, `iss`, `aud`, `iat` and `exp`; `iss` and `aud` are verified on every request. HS256 remains available through configuration for simple local setups.

## Consequences
- Verifiers need no secrets and cannot forge tokens.
- Key files must be provisioned outside the image (`scripts/generate_jwt_keys.py`); production refuses to start without them, and development falls back to an ephemeral key pair.
- The `roles` claim is a snapshot. Authorization decisions still go through the validation APIs, so role changes and deactivation apply immediately.
