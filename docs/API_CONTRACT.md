# Identity Service: Cross-Service API Contract

**Owner:** Group 5 (Identity & University Directory) · **Contract version:** v1 (`/api/v1`) · **Status:** ready for integration

**Audience:** Groups 6, 7 and 8, the shared frontend team and the API Gateway team.

This document defines how other services authenticate users and check identity, roles and eligibility through the Identity Service. All examples below are real responses captured from the service with synthetic demo data.

---

## 1. Principles

1. **Source of truth.** The Identity Service owns users, roles, permissions and account status. The University Directory Service (also Group 5) owns faculties, departments, service units, affiliations and service responsibilities.
2. **APIs only.** Never read the Identity or Directory databases, and never keep your own copy of users or roles as if it were authoritative. Store the `user_id` and validate it through these APIs when a decision depends on it.
3. **Server-side decisions.** A valid JWT proves who the caller is, not what they may do. Check role, status and responsibility through the validation APIs before protected actions.
4. **Versioned contract.** Everything in this document is under `/api/v1`. Breaking changes will get a new version and will be announced before they ship. Adding a field is not a breaking change, so ignore fields you don't recognise.

## 2. Base URLs and the API Gateway

| | Value |
|---|---|
| Internal service base URL | **Configurable.** Local default `http://localhost:8001`. In Docker Compose, use the service name (e.g. `http://identity-service:8001`) |
| API prefix | `/api/v1` |
| Swagger / OpenAPI | `{base}/docs` · `{base}/openapi.json` |
| Health | `GET {base}/health` (no auth) |
| Signing keys | `GET {base}/.well-known/jwks.json` (no auth) |
| **Gateway base path** | **To be confirmed by the API Gateway team** |

**Suggested gateway route (to be confirmed):** route `/identity/**` to the Identity Service and strip the `/identity` prefix, so that `GET {gateway}/identity/api/v1/auth/me` reaches `GET /api/v1/auth/me`. Services shouldn't hard-code a gateway path; read the Identity base URL from configuration (for example `IDENTITY_SERVICE_BASE_URL`).

Every response has an `X-Request-ID` header. If the gateway sends `X-Request-ID`, the service reuses it, so one request can be traced across services.

## 3. Authentication and JWT

### 3.1 Getting a token

`POST /api/v1/auth/login` (no auth)

```json
{ "username": "SDO001", "password": "••••••••" }
```
`username` is the university ID or the email address.

**200 OK**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6Ii4uLiJ9.eyJzdWIiOiIuLi4ifQ.signature",
    "token_type": "bearer",
    "expires_in": 3600,
    "user_id": "usr-servicedesk-001",
    "university_id": "SDO001",
    "roles": ["SERVICE_DESK_OFFICER"]
  }
}
```

| Status | `error.code` | When |
|---|---|---|
| 401 | `INVALID_CREDENTIALS` | Unknown user, wrong password or no password set (one response for all three, so accounts can't be probed) |
| 403 | `ACCOUNT_INACTIVE` | Correct credentials, but the account is deactivated |
| 422 | `VALIDATION_ERROR` | Malformed body |

Send the token on every call: `Authorization: Bearer <access_token>`.

### 3.2 Token format (JWT claim structure)

Header: `{"alg": "RS256", "kid": "<key id>", "typ": "JWT"}`

| Claim | Example | Meaning |
|---|---|---|
| `sub` | `usr-servicedesk-001` | **Stable user ID.** Use this to reference users in your data |
| `university_id` | `SDO001` | Human-facing university identifier |
| `account_type` | `STAFF` | `STUDENT` or `STAFF` |
| `roles` | `["SERVICE_DESK_OFFICER"]` | Roles **at login time** (snapshot, see below) |
| `iss` | `university-identity-service` | Issuer (must match) |
| `aud` | `university-services-platform` | Audience (must match) |
| `iat` / `exp` | Unix seconds | Issued at / expiry (default lifetime 60 minutes) |

**Required checks when verifying a token:** RS256 signature against the JWKS key whose `kid` matches the token header, `exp` not passed, `iss == university-identity-service`, `aud == university-services-platform`, and `sub` present.

**`roles` is a snapshot.** Use it for routing, menus and UI. An administrator may change roles or deactivate the account after the token was issued. Before a protected action, confirm through `GET /api/v1/validation/users/{user_id}` or the eligibility endpoint.

### 3.3 Verifying tokens (API Gateway and other services)

- Fetch `GET /.well-known/jwks.json` and cache it. If a token has an unknown `kid`, fetch it again.
- The Identity Service holds the only private key. Other services can **verify** tokens but cannot **create** them, and there is no shared secret to distribute.

```json
{
  "keys": [{
    "kty": "RSA", "alg": "RS256", "use": "sig",
    "kid": "9w8BsZMqqNMxjik0a8U0DIw_mMBkNXDCHRPZyHJOj8c",
    "n": "ypxgvmkwQx-B14lE_SrOx…", "e": "AQAB"
  }]
}
```

### 3.4 Service-to-service calls

When your service calls the Identity validation APIs while handling a user's request, **forward that user's `Authorization` header**. The validation endpoints accept the token of any **active** user; the user being validated can be someone else.

## 4. Error contract

Every error, on every endpoint, has the same shape:

```json
{
  "success": false,
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "User with identifier 'usr-unknown-999' was not found."
  },
  "timestamp": "2026-09-26T10:15:30.123Z"
}
```

- Branch on `error.code`, which is stable. `error.message` is human-readable and may change.
- `422` responses add `error.details: [{ "field", "message", "type" }]`.
- `500` responses never contain internal details.

| Status | Meaning | Codes |
|---|---|---|
| 400 | Malformed identifier or request | `INVALID_IDENTIFIER_FORMAT`, `INVALID_CURRENT_PASSWORD`, `BAD_REQUEST` |
| 401 | Not authenticated | `UNAUTHORIZED` (no token), `INVALID_TOKEN` (bad signature, expired, wrong iss/aud), `USER_NOT_FOUND` (token for a deleted user), `INVALID_CREDENTIALS` (login) |
| 403 | Authenticated but not allowed | `ACCOUNT_INACTIVE`, `INSUFFICIENT_PERMISSIONS`, `FORBIDDEN_PROFILE_ACCESS` |
| 404 | Resource not found | `USER_NOT_FOUND`, `ROLE_NOT_FOUND`, `ROLE_NOT_ASSIGNED`, `NOT_FOUND` |
| 409 | Conflict | `UNIVERSITY_ID_ALREADY_EXISTS`, `EMAIL_ALREADY_EXISTS`, `ROLE_ALREADY_ASSIGNED` |
| 422 | Request validation failed | `VALIDATION_ERROR` |
| 500 | Unexpected server error | `INTERNAL_SERVER_ERROR` |
| 502 | Directory Service answered outside its contract | `DEPENDENCY_ERROR` |
| 503 | Directory Service unavailable | `DEPENDENCY_UNAVAILABLE` (retry later; **never treat as "eligible"**) |

**Examples**

401: no token
```json
{ "success": false, "error": { "code": "UNAUTHORIZED", "message": "Authentication credentials were not provided." }, "timestamp": "2026-09-26T10:15:30.123Z" }
```
401: invalid or expired token
```json
{ "success": false, "error": { "code": "INVALID_TOKEN", "message": "Authentication token is invalid or expired." }, "timestamp": "2026-09-26T10:15:30.123Z" }
```
403: missing permission
```json
{ "success": false, "error": { "code": "INSUFFICIENT_PERMISSIONS", "message": "User does not have the required permission: 'audit:read'" }, "timestamp": "2026-09-26T10:15:30.123Z" }
```

## 5. Which endpoint answers which question

| Question | Endpoint | Section |
|---|---|---|
| Who is the logged-in user? (identity validation) | `GET /api/v1/auth/me` | 6.1 |
| Does user X exist, and is the account active? (user validation) | `GET /api/v1/validation/users/{user_id}` | 6.2 |
| Does user X hold role R? (role validation) | same, with `?required_role=R` | 6.2 |
| Which roles exist? | `GET /api/v1/roles` | 6.4 |
| Is X affiliated with department D or faculty F? (affiliation, department validation) | `GET /api/v1/validation/users/{user_id}/eligibility?relationship=AFFILIATION&department_id=D` | 6.3 |
| Is X responsible for service unit S or department D? (responsibility, service-unit validation) | `…/eligibility?relationship=RESPONSIBILITY&service_unit_id=S` | 6.3 |
| Role **and** responsibility together (key business rule) | `…/eligibility?required_role=R&relationship=RESPONSIBILITY&…` | 6.3 |
| Does faculty, department or service unit Z exist, and what are its details? | **Directory Service** API | 7 |

## 6. Endpoints

### 6.1 Current identity

`GET /api/v1/auth/me` · **Auth:** Bearer (active account) · **Authorization:** none beyond an active account

Returns the caller's identity, roles and Identity Service permissions, read live from the database. Intended for the frontend's profile page and role-aware navigation.

**200 OK**
```json
{
  "success": true,
  "data": {
    "user_id": "usr-servicedesk-001",
    "university_id": "SDO001",
    "name": "Demo Service Desk Officer",
    "email": "sdo001@university.example",
    "account_type": "STAFF",
    "status": "ACTIVE",
    "roles": ["SERVICE_DESK_OFFICER"],
    "primary_role": "SERVICE_DESK_OFFICER",
    "permissions": ["profile:read_own"]
  }
}
```
Errors: `401 UNAUTHORIZED` / `INVALID_TOKEN`, `403 ACCOUNT_INACTIVE`.

### 6.2 User and role validation

`GET /api/v1/validation/users/{user_id}` · **Auth:** Bearer (any active user; forward your user's token)

| Parameter | In | Required | Description |
|---|---|---|---|
| `user_id` | path | yes | Internal ID (`usr-…`) **or** university ID (`STU001`) |
| `required_role` | query | no | Role to check (case-insensitive) |
| `require_active` | query | no (default `false`) | `true` returns 403 for inactive accounts |

Example request: `GET /api/v1/validation/users/TEC001?required_role=TECHNICIAN`

**200 OK**: user exists and holds the role
```json
{
  "success": true,
  "data": {
    "user_id": "usr-technician-001",
    "university_id": "TEC001",
    "name": "Demo Technician",
    "account_type": "STAFF",
    "status": "ACTIVE",
    "is_valid": true,
    "roles": ["TECHNICIAN"],
    "is_authorized": true,
    "required_role_checked": "TECHNICIAN"
  }
}
```

**200 OK**: role not held (a missing role is reported in the body, not as an error status)
```json
{
  "success": true,
  "data": {
    "user_id": "usr-student-001", "university_id": "STU001", "name": "Demo Student",
    "account_type": "STUDENT", "status": "ACTIVE", "is_valid": true, "roles": ["STUDENT"],
    "is_authorized": false, "required_role_checked": "RESOURCE_MANAGER"
  }
}
```

**How to read the result:**
- `is_valid` is `true` exactly when `status == "ACTIVE"`.
- `is_authorized` is `false` only when `required_role` was given and the user doesn't hold it.
- **A user may act only when both are `true`.**

| Status | `error.code` | When |
|---|---|---|
| 404 | `USER_NOT_FOUND` | Unknown user |
| 403 | `ACCOUNT_INACTIVE` | Inactive account **and** `require_active=true` (without it: 200 with `is_valid: false`) |
| 400 | `INVALID_IDENTIFIER_FORMAT` | Identifier isn't 3–50 characters of `[A-Za-z0-9_-]` |
| 401 | `UNAUTHORIZED` / `INVALID_TOKEN` | Missing or invalid caller token |

Unknown user:
```json
{ "success": false, "error": { "code": "USER_NOT_FOUND", "message": "User with identifier 'usr-unknown-999' was not found." }, "timestamp": "2026-09-26T10:15:30.123Z" }
```
Inactive user (`require_active=true`):
```json
{ "success": false, "error": { "code": "ACCOUNT_INACTIVE", "message": "User account is inactive." }, "timestamp": "2026-09-26T10:15:30.123Z" }
```

The response doesn't include contact details such as email. Other services only need identity, status and roles.

### 6.3 Eligibility: identity + role + organizational relationship

`GET /api/v1/validation/users/{user_id}/eligibility` · **Auth:** Bearer (any active user; forward your user's token)

This implements the platform's key business rule: *not every staff member has the same permissions; authorization considers both system role and relevant department or service responsibility.*

| Parameter | Required | Description |
|---|---|---|
| `user_id` (path) | yes | Internal or university ID |
| `required_role` | no | Role the user must hold |
| `relationship` | when a unit is given | `AFFILIATION`: the user **belongs to** the department or faculty (e.g. a student's department). `RESPONSIBILITY`: the user **is responsible for** the unit (e.g. a service desk or resource manager) |
| `department_id` | no | Directory department ID (`AFFILIATION` also accepts the department **code**) |
| `faculty_id` | no | Directory faculty ID (`AFFILIATION` also accepts the faculty **code**) |
| `service_unit_id` | no | Directory service unit ID (`RESPONSIBILITY` only) |

**Response fields:**
- `eligible` is `true` only when **every** requested check passes.
- `reasons` lists machine-readable causes. `message` is a clear explanation you can show to the user.
- `checks` shows each individual result (`null` means not requested or not evaluated).
- `matched_responsibilities` and `affiliation` are included for display.

**Reason codes:** `ACCOUNT_INACTIVE`, `ROLE_NOT_HELD`, `NO_AFFILIATION`, `AFFILIATION_MISMATCH`, `NO_MATCHING_RESPONSIBILITY`, `RESPONSIBILITY_INACTIVE`.

**Order of evaluation:** first account and role (Identity DB), then, only if those pass, the relationship (Directory Service). An inactive or wrong-role user is therefore rejected even while the Directory Service is down.

**Example A: service desk officer responsible for a service unit (eligible)**
`GET /api/v1/validation/users/SDO001/eligibility?required_role=SERVICE_DESK_OFFICER&relationship=RESPONSIBILITY&service_unit_id=su-it-helpdesk`
```json
{
  "success": true,
  "data": {
    "user_id": "usr-servicedesk-001",
    "university_id": "SDO001",
    "account_status": "ACTIVE",
    "roles": ["SERVICE_DESK_OFFICER"],
    "eligible": true,
    "reasons": [],
    "message": "User is eligible.",
    "checks": {
      "account_active": true,
      "required_role": "SERVICE_DESK_OFFICER",
      "role_held": true,
      "relationship": "RESPONSIBILITY",
      "relationship_satisfied": true
    },
    "matched_responsibilities": [{
      "responsibility_id": "rsp-7f3a",
      "role_title": "Service Desk Lead",
      "service_unit_id": "su-it-helpdesk",
      "service_unit_name": "IT Help Desk",
      "department_id": null, "department_name": null,
      "faculty_id": null, "faculty_name": null
    }],
    "affiliation": null
  }
}
```

**Example B: correct role, but no responsibility for that unit (invalid relationship)**
```json
{
  "success": true,
  "data": {
    "user_id": "usr-technician-001", "university_id": "TEC001", "account_status": "ACTIVE", "roles": ["TECHNICIAN"],
    "eligible": false,
    "reasons": ["NO_MATCHING_RESPONSIBILITY"],
    "message": "User has no responsibility for the requested organizational unit.",
    "checks": { "account_active": true, "required_role": "TECHNICIAN", "role_held": true,
                "relationship": "RESPONSIBILITY", "relationship_satisfied": false },
    "matched_responsibilities": [], "affiliation": null
  }
}
```

**Example C: student in a department-restricted event (affiliation, matched by department code)**
`GET …/users/STU001/eligibility?required_role=STUDENT&relationship=AFFILIATION&department_id=CS`
```json
{
  "success": true,
  "data": {
    "user_id": "usr-student-001", "university_id": "STU001", "account_status": "ACTIVE", "roles": ["STUDENT"],
    "eligible": true, "reasons": [], "message": "User is eligible.",
    "checks": { "account_active": true, "required_role": "STUDENT", "role_held": true,
                "relationship": "AFFILIATION", "relationship_satisfied": true },
    "matched_responsibilities": [],
    "affiliation": { "department_id": "dep-cs", "department_name": "Department of Computer Science",
                     "faculty_id": "fac-sci", "faculty_name": "Faculty of Science" }
  }
}
```

**Example D: affiliated with a different department**
```json
{ "…": "…", "eligible": false, "reasons": ["AFFILIATION_MISMATCH"],
  "message": "User is not affiliated with the requested department/faculty." }
```

**Example E: invalid role**
```json
{ "…": "…", "eligible": false, "reasons": ["ROLE_NOT_HELD"], "message": "User does not hold the required role.",
  "checks": { "account_active": true, "required_role": "RESOURCE_MANAGER", "role_held": false,
              "relationship": null, "relationship_satisfied": null } }
```

**Example F: inactive user**
```json
{ "…": "…", "account_status": "INACTIVE", "eligible": false, "reasons": ["ACCOUNT_INACTIVE"],
  "message": "User account is inactive." }
```

| Status | `error.code` | When |
|---|---|---|
| 404 | `USER_NOT_FOUND` | Unknown user |
| 422 | `VALIDATION_ERROR` | A unit without `relationship`, `relationship` without a unit, or `AFFILIATION` with `service_unit_id` |
| 503 | `DEPENDENCY_UNAVAILABLE` | Directory Service needed but unreachable, timed out or returned 5xx. **Treat as "unknown", not "eligible"** |
| 502 | `DEPENDENCY_ERROR` | Directory Service returned an unexpected response |
| 401 | `UNAUTHORIZED` / `INVALID_TOKEN` | Missing or invalid caller token |

```json
{ "success": false, "error": { "code": "DEPENDENCY_UNAVAILABLE", "message": "The Directory Service is currently unavailable, so eligibility could not be determined. Please retry later." }, "timestamp": "2026-09-26T10:15:30.123Z" }
```
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "'relationship' is required when an organizational unit is given.",
  "details": [{ "field": "query.relationship", "message": "'relationship' is required when an organizational unit is given.", "type": "value_error" }] },
  "timestamp": "2026-09-26T10:15:30.123Z" }
```

### 6.4 Roles

`GET /api/v1/roles` and `GET /api/v1/roles/{role_name}` · **Auth:** Bearer · **Authorization:** permission `roles:read` (ADMIN, STAFF)

**Role identifiers (stable, uppercase):**

| Role | Platform meaning |
|---|---|
| `ADMIN` | System administrator |
| `STAFF` | General staff member (Sprint 1 role) |
| `STUDENT` | Student |
| `ACADEMIC_STAFF` | Reserves teaching or meeting resources, organizes events |
| `ADMINISTRATIVE_STAFF` | Manages service information, approves reservations, publishes announcements |
| `SERVICE_DESK_OFFICER` | Triages service requests |
| `TECHNICIAN` | Works on assigned work orders |
| `RESOURCE_MANAGER` | Maintains facilities and resources, approves reservations |
| `EVENT_ORGANIZER` | Creates events, manages registrations |

**User-role relationship:**
- A user can hold several roles; `primary_role` is the first one.
- A user with no assigned role is treated as having their `account_type` (`STUDENT` or `STAFF`) as the role.
- Only ADMIN can assign, update or revoke roles. Every change is audited and applies immediately.

`GET /api/v1/users/{user_id}/role` (any active user) returns `{user_id, university_id, name, account_type, roles, primary_role}`.

## 7. Faculty, department and service-unit data (Directory Service)

The Identity Service **does not duplicate** directory data. To look up or validate faculties, departments and service units themselves, call the **University Directory Service** (Group 5). Its base URL is configurable; the Sprint 1 default is `http://localhost:8002`:

| Purpose | Directory Service endpoint |
|---|---|
| Validate a faculty | `GET /validation/faculties/{faculty_id}` |
| Validate a department | `GET /validation/departments/{department_id}` |
| Validate a service unit | `GET /validation/service-units/{unit_id}` |
| A user's service responsibilities | `GET /validation/users/{user_id}/responsibilities` |
| A user's affiliation | `GET /affiliations/users/{user_id}` |
| Browse or search | `GET /faculties`, `/departments`, `/service-units`, `/affiliations` |

The exact response formats are in the Directory Service's own OpenAPI (`{directory}/docs`). For decisions that combine **a user** with a unit, use the Identity eligibility endpoint (6.3). It checks account, role and relationship together, handles Directory failures safely, and gives one answer.

## 8. Notes for Group 6 (Facilities and Reservations)

Group 6 asked Group 5 for the following:

| Request | Answer |
|---|---|
| User validation API | §6.2 `GET /api/v1/validation/users/{user_id}` |
| Role validation and JWT claim structure | §6.2 with `required_role`; claims in §3.2; verification in §3.3 |
| Department and service-unit data for eligibility rules | §6.3 eligibility (`relationship=AFFILIATION` or `RESPONSIBILITY`); unit details from the Directory Service (§7) |
| Sample JSON | §3, §4 and §6 (all captured from the running service) |
| 401 / 403 / 404 errors | §4 and each endpoint's table |
| Gateway route and base path | §2 (suggested `/identity/**` → `/api/v1`, **to be confirmed** by the Gateway team) |

**Example: may this user approve a reservation for a resource owned by department `dep-cs`?**
```
GET /api/v1/validation/users/{approver_id}/eligibility
    ?required_role=RESOURCE_MANAGER&relationship=RESPONSIBILITY&department_id=dep-cs
```
Approve only if `data.eligible == true`; otherwise show `data.message`. On `503`, don't approve; ask the user to retry.

**Group 6's own API:** Group 6's venue-validation endpoints (`GET /api/resources/{id}/validate/group8`, `GET /api/resources/code/{code}/validate` on `facility-resource-service`) are **not** consumed by the Identity Service. No Identity feature needs venue data, and Group 5 consumes no other team's domain data. If that changes, a client will be added behind a configurable `GROUP6_BASE_URL`, using the same patterns as the Directory client (timeouts, safe error mapping, and relying on `data.validForReservation` / `data.message`).

## 9. Legacy (Sprint 1) routes

The unversioned routes (`/users…`, `/validation/users/{id}`, `/protected/*`) still work so that existing consumers don't break. They are **deprecated**: responses carry `Deprecation: true` and `Link: </api/v1/…>; rel="successor-version"`. Note that legacy `GET /validation/users/{id}` is unauthenticated and includes `email`, while the v1 endpoint needs a token and omits email. **Please migrate to `/api/v1`.** Removal will be announced in advance.

## 10. Integration checklist for consumers

- [ ] Read the Identity base URL from configuration; don't hard-code gateway paths.
- [ ] Verify JWTs using JWKS: signature, `exp`, `iss`, `aud`.
- [ ] Store users by `sub` / `user_id`, not by name or email.
- [ ] Before protected actions, call §6.2 or §6.3 with the user's forwarded token.
- [ ] Branch on `error.code`; show `error.message` or `data.message` to users.
- [ ] Treat `503 DEPENDENCY_UNAVAILABLE` as "try again later", never as "allowed".
- [ ] Ignore response fields you don't recognise.

## 11. Change log

| Version | Change |
|---|---|
| v1 | Initial versioned contract: login and JWT (RS256, JWKS), `/auth/me`, user/role validation, eligibility (affiliation and responsibility), role catalogue, audit log, standard error envelope. Sprint 1 routes kept as deprecated aliases. |
