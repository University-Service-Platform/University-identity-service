# University Identity Service

Group 5 · University Services Management Platform (`identity-access-service`)

The Identity Service is the source of truth for **users, roles, permissions, account status and authentication** on the platform. It issues the JWTs that every other service accepts, and it lets other services validate users, roles and eligibility through documented APIs. Other services never read its database.

Faculties, departments, service units, affiliations and service responsibilities belong to the **University Directory Service** (also Group 5). The Identity Service reads that data through the Directory Service's API and never copies it.

---

## 1. Architecture

```
            Shared frontend / API Gateway / Groups 6, 7, 8
                               │  HTTPS + Bearer JWT
                               ▼
┌──────────────────────── Identity Service ────────────────────────┐
│ routes/        HTTP layer (FastAPI routers, /api/v1 + legacy)    │
│ dependencies/  authentication & role/permission checks           │
│ services/      business rules (users, roles, login, eligibility) │
│ repositories/  data access (SQLAlchemy)                          │
│ integrations/  Directory Service HTTP client                     │
│ core/          config, security (bcrypt, JWT), errors, logging   │
└───────────┬──────────────────────────────────────┬───────────────┘
            │ SQLAlchemy                           │ HTTP (httpx)
            ▼                                      ▼
   Identity DB (owned)                    Directory Service API
   users, roles, user_roles,              affiliations, responsibilities
   permissions, role_permissions,         (faculties, departments,
   audit_logs                              service units)
```

- **Data ownership:** only this service reads or writes the Identity DB.
- **Authorization:** checked on the server for every request. Roles and account status are read from the database on each request, not trusted from the token, so role changes and deactivation apply immediately.
- **Dependency failures:** if the Directory Service is down, profiles still load (`affiliation_status: UNAVAILABLE`). Eligibility checks that need it return `503 DEPENDENCY_UNAVAILABLE` and never guess.

## 2. Technologies

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, python-jose (JWT, RS256), bcrypt, httpx, pytest. SQLite by default; any SQLAlchemy database works through `DATABASE_URL`.

## 3. Local setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # then edit values (never commit .env)
python scripts/generate_jwt_keys.py   # optional in development, required in production
```

`.env` is not loaded automatically. Export the variables in your shell or use Docker Compose (section 11). Without any variables the service runs with development defaults.

## 4. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` turns on the startup checks below |
| `DATABASE_URL` | `sqlite:///./identity.db` | Identity DB (owned by this service only) |
| `JWT_ALGORITHM` | `RS256` | `RS256` (recommended) or `HS256` |
| `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` | *(empty)* | RS256 key files. Empty in development means an ephemeral key pair is used; **required in production** |
| `JWT_SECRET_KEY` | development value | HS256 only; the default is **rejected in production** |
| `JWT_ISSUER` | `university-identity-service` | `iss` claim, checked on every request |
| `JWT_AUDIENCE` | `university-services-platform` | `aud` claim, checked on every request |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime |
| `DIRECTORY_SERVICE_BASE_URL` | *(empty = disabled)* | e.g. `http://localhost:8002` |
| `DIRECTORY_SERVICE_TIMEOUT_SECONDS` | `3` | Timeout for Directory Service calls |
| `DEMO_USER_PASSWORD` | *(empty)* | Password given to seeded demo users |
| `SEED_DEMO_DATA` | `false` | Container only: seed demo users on start |
| `LOG_LEVEL` | `INFO` | Logging level |

## 5. Database setup and migrations

The schema is managed by **Alembic** (`migrations/versions/`):

| Revision | Change |
|---|---|
| 0001 | Sprint 1 schema: `users`, `roles`, `user_roles` |
| 0002 | Unique constraint on `user_roles(user_id, role_id)` |
| 0003 | `permissions`, `role_permissions` |
| 0004 | `users.password_hash` |
| 0005 | `audit_logs` |

```bash
alembic upgrade head                  # create or upgrade the schema
python -m app.seed                    # system roles + permissions (safe to re-run)
DEMO_USER_PASSWORD=<choose> python -m app.seed --demo   # + synthetic demo users
alembic current                       # show the applied revision
alembic downgrade -1                  # roll back one revision
```

An `identity.db` created by Sprint 1 code (before migrations existed) must be marked once with `alembic stamp 0001`, then run `alembic upgrade head`.

**Synthetic demo users** (created by `--demo`, all with password `DEMO_USER_PASSWORD`):

| University ID | Role | Notes |
|---|---|---|
| ADM001 | ADMIN | System administrator |
| STF001 | STAFF | |
| STU001 | STUDENT | |
| STU002 | STUDENT | **Inactive** (for testing rejection) |
| ACD001 | ACADEMIC_STAFF | |
| ADS001 | ADMINISTRATIVE_STAFF | |
| SDO001 | SERVICE_DESK_OFFICER | |
| TEC001 | TECHNICIAN | |
| RMG001 | RESOURCE_MANAGER | |
| EVO001 | EVENT_ORGANIZER | |

All data is synthetic. Never load real student or staff records.

## 6. Running the service

```bash
alembic upgrade head && python -m app.seed
uvicorn app.main:app --port 8001 --reload
```

- Swagger UI: http://localhost:8001/docs · ReDoc: http://localhost:8001/redoc · OpenAPI JSON: http://localhost:8001/openapi.json
- Health: `GET /health` · Public signing keys: `GET /.well-known/jwks.json`

## 7. API overview

> **Integrating from another service?** Read the cross-service contract in [docs/API_CONTRACT.md](docs/API_CONTRACT.md). It covers the JWT claim structure, user, role and eligibility validation, error codes, sample JSON, the gateway recommendation and notes for Group 6. Design decisions are recorded in [docs/adr/](docs/adr/).

All endpoints below are under **`/api/v1`**. Responses use `{"success": true, "data": ...}`.

| Area | Method & path | Access |
|---|---|---|
| Auth | `POST /auth/login` | Public |
| | `GET /auth/me` | Any active user |
| | `POST /auth/change-password` | Any active user |
| Users | `POST /users` · `PUT /users/{id}` · `DELETE /users/{id}` | ADMIN |
| | `GET /users` | ADMIN, STAFF |
| | `GET /users/{id}` (profile + directory affiliation) | Self, ADMIN, STAFF |
| | `PATCH /users/{id}/status` | ADMIN |
| | `PUT /users/{id}/password` | `users:manage` |
| Roles | `GET /users/{id}/role` | Any active user |
| | `POST /users/{id}/roles` · `PUT /users/{id}/roles` · `DELETE /users/{id}/roles/{role}` | ADMIN |
| | `GET /roles` · `GET /roles/{name}` | `roles:read` |
| Validation (for other services) | `GET /validation/users/{id}` | Token of any active user |
| | `GET /validation/users/{id}/eligibility` | Token of any active user |
| Audit | `GET /audit-logs` | `audit:read` |

The Sprint 1 unversioned paths (`/users`, `/validation/users/{id}`, `/protected/*`) still work as **deprecated aliases**. They are marked deprecated in OpenAPI and return `Deprecation: true` plus a `Link` header naming the successor endpoint.

## 8. Authentication

1. `POST /api/v1/auth/login` with `{"username": "<university ID or email>", "password": "..."}`.
2. Send the returned `access_token` as `Authorization: Bearer <token>`.

- Passwords are stored as **bcrypt** hashes. Unknown users, wrong passwords and accounts without a password all get the same `401 INVALID_CREDENTIALS`. Inactive accounts get `403 ACCOUNT_INACTIVE`.
- Tokens are **RS256**-signed. The public key is at `/.well-known/jwks.json`, so the API Gateway and other services can **verify** tokens but cannot **issue** them.
- **Claims:** `sub` (user ID), `university_id`, `account_type`, `roles`, `iss`, `aud`, `iat`, `exp`.
- The `roles` claim is a snapshot taken at login. Use it for routing and UI, and use the validation APIs for authorization decisions.

## 9. Authorization

- **Roles:** ADMIN, STAFF, STUDENT (Sprint 1), plus ACADEMIC_STAFF, ADMINISTRATIVE_STAFF, SERVICE_DESK_OFFICER, TECHNICIAN, RESOURCE_MANAGER and EVENT_ORGANIZER. A user with no assigned role is treated as having their account type as the role.
- **Permissions (owned by this service):** `profile:read_own`, `users:read`, `users:manage`, `users:manage_status`, `roles:read`, `roles:assign`, `audit:read`. `GET /roles` lists which role grants which permission.
- **Responsibility-aware authorization:** the key business rule is that staff with the same role don't all have the same permissions. `GET /api/v1/validation/users/{id}/eligibility` combines role with the user's department affiliation or service responsibility from the Directory Service.
- **Audit trail:** user creation, update, status change and deletion; role assignment, update and revocation; password set and change; and successful logins are all recorded in `audit_logs` (`GET /api/v1/audit-logs`).

## 10. Error responses

Every error uses one envelope:

```json
{
  "success": false,
  "error": { "code": "USER_NOT_FOUND", "message": "User with identifier 'usr-x' was not found." },
  "timestamp": "2026-09-26T10:15:30.123Z"
}
```

`422` responses add `error.details` (`field`, `message`, `type`). `500` responses never expose internal details. Every response carries an `X-Request-ID` header; a value sent by the gateway is reused.

## 11. Docker

```bash
DEMO_USER_PASSWORD=<choose-one> docker compose up --build
# Swagger UI: http://localhost:8001/docs
```

On start the container runs `alembic upgrade head`, then `python -m app.seed` (with `--demo` when `SEED_DEMO_DATA=true`, which is the Compose default), then uvicorn. Data lives in the `identity-data` volume. The image runs as a non-root user and includes a health check.

For persistent RS256 keys, generate them with `scripts/generate_jwt_keys.py`, mount the folder into the container and set `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH`. Never bake keys into the image.

## 12. Testing

```bash
pytest -q
```

| Suite | Covers |
|---|---|
| `test_user_*`, `test_account_*`, `test_role_*`, `test_profile_access.py` | Sprint 1 behavior (unchanged) |
| `test_authentication.py` | Login, JWT claims and verification, JWKS, passwords |
| `test_role_catalogue.py`, `test_current_identity.py`, `test_audit_log.py` | Roles, permissions, `/auth/me`, audit trail |
| `test_api_versioning.py`, `test_error_contract.py` | `/api/v1` and legacy aliases, error envelope |
| `test_directory_client.py`, `test_eligibility.py`, `test_profile_affiliation.py` | Directory integration: success, timeout, connection failure, 5xx, invalid payload |
| `test_migrations_and_seed.py` | Migrations match the models, upgrade and downgrade, seed is idempotent |
| `test_e2e_workflows.py` | Full workflows on a migrated and seeded database |
| `test_consumer_contracts.py` | Groups 6, 7 and 8 using the documented contract |

No test calls a real external service; the Directory Service is replaced by `httpx.MockTransport`.

**Postman:** import `docs/postman/identity-service.postman_collection.json` and `docs/postman/identity-service.local.postman_environment.json`, set `demoPassword`, then run the collection. The login request stores the token for the requests that follow, and each request has status-code tests.

## 13. Project layout

```
app/             service code (see Architecture)
migrations/      Alembic environment and versioned migrations
scripts/         generate_jwt_keys.py, start.py (container entrypoint)
tests/           automated tests
docs/postman/    Postman collection and environment
```
