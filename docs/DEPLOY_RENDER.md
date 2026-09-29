# Deploying the Identity Service on Render

The repository contains a Render Blueprint ([`render.yaml`](../render.yaml)) that creates:

- **`university-identity-service`**: a free Docker web service built from the `Dockerfile`
- **`identity-db`**: a free Postgres database, connected through `DATABASE_URL`

On every start the container runs the migrations, seeds the roles and permissions (plus the synthetic demo users), and starts the API. Nothing has to be run by hand after a deploy.

## Before you start

- A Render account. Sign up with GitHub so Render can see the repository. Because the repository belongs to the `University-Service-Platform` organisation, an organisation owner may have to approve the Render GitHub app for it.
- The code you want to deploy merged into **`main`**. The Blueprint deploys `main` and redeploys automatically on every push to it.
- Python with the project's requirements installed locally (for step 1).

## 1. Create the JWT signing keys (once)

```bash
python scripts/generate_jwt_keys.py
```

This writes `keys/jwt_private.pem` and `keys/jwt_public.pem`. The `keys/` folder is git-ignored. **Never commit these files or share the private key.**

Keep both files safe and reuse them. New keys would invalidate every token that has been issued, and the other groups' services would have to fetch the JWKS again.

## 2. Create the Blueprint

1. Render dashboard → **New** → **Blueprint**.
2. Select the `University-identity-service` repository. Render reads `render.yaml`.
3. Render asks for the values marked `sync: false`:

   | Variable | What to enter |
   |---|---|
   | `DEMO_USER_PASSWORD` | A password for the demo users (e.g. `STU001`, `RMG001`). Share it with other groups privately |
   | `DIRECTORY_SERVICE_BASE_URL` | The Directory Service's Render URL, or leave empty until it is deployed |
   | `CORS_ALLOWED_ORIGINS` | Leave empty if browsers go through the API Gateway; otherwise the frontend URL |

4. Click **Apply**.

**The first deploy fails, and that is expected.** The service runs with `ENVIRONMENT=production`, which refuses to start without signing keys. Step 3 adds them. The log shows:
`JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH must be set` or a missing file under `/etc/secrets/`.

## 3. Upload the keys as Secret Files

Blueprints cannot contain secret files, so add them once in the dashboard:

1. Open **university-identity-service** → **Environment** → **Secret Files** → **Add Secret File**.
2. Filename `jwt_private.pem`; contents: paste the whole of `keys/jwt_private.pem`, including the `-----BEGIN` and `-----END` lines.
3. Add a second file, `jwt_public.pem`, with the contents of `keys/jwt_public.pem`.
4. **Save changes**, then **Manual Deploy** → **Deploy latest commit**.

Render mounts the files at `/etc/secrets/jwt_private.pem` and `/etc/secrets/jwt_public.pem`, the paths already set in `render.yaml`.

## 4. Check the deployment

Replace `<url>` with the service URL shown in the dashboard (for example `https://university-identity-service.onrender.com`).

| Check | Expected |
|---|---|
| `GET <url>/health` | `{"status": "healthy", ...}` |
| `GET <url>/.well-known/jwks.json` | One RSA key |
| `<url>/docs` | Swagger UI |
| Log in (below) | `200` with an `access_token` |

```bash
curl -X POST <url>/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "STU001", "password": "<DEMO_USER_PASSWORD>"}'
```

## 5. Give the other groups

| What | Value |
|---|---|
| Base URL | `<url>` (API under `/api/v1`) |
| JWKS for verifying tokens | `<url>/.well-known/jwks.json` |
| Issuer / audience | `university-identity-service` / `university-services-platform` |
| Demo users | `STU001` (student), `RMG001` (resource manager), `SDO001`, `TEC001`, `ADM001` and others; see the README |
| Demo password | Send privately |

Spring services verify tokens with
`spring.security.oauth2.resourceserver.jwt.jwk-set-uri=<url>/.well-known/jwks.json`.

## Free plan limits

| Limit | What it means | What to do |
|---|---|---|
| Service sleeps after 15 minutes without traffic | The next request takes about a minute | Open `<url>/health` a few minutes before a demo. Callers need generous timeouts |
| 750 free instance hours per workspace each month | Enough for one always-on service | Host each group's services in that group's own Render workspace |
| Free Postgres expires 30 days after creation | The database and its data are deleted | Before it expires, create a new database and point `DATABASE_URL` at it. Demo data is re-created on the next start; anything else is lost. Or use a free external Postgres (Neon, Supabase): set `DATABASE_URL` to its URL in the dashboard |
| One free Postgres per workspace | Other services in the same workspace can't get their own | Same as above |

Any Postgres URL works: `postgres://…`, `postgresql://…` and `postgresql+psycopg://…` are all accepted.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Deploy fails with a signing-key error | Secret Files missing or misnamed (step 3). Names must be exactly `jwt_private.pem` and `jwt_public.pem` |
| Tokens stop working after a deploy | The keys were replaced. Upload the original files again, or ask all groups to log in again |
| Login returns `401 INVALID_CREDENTIALS` for demo users | `DEMO_USER_PASSWORD` differs from what you typed. Demo passwords are only set when the users are first created; changing the variable later does not change existing passwords |
| Eligibility returns `503 DEPENDENCY_UNAVAILABLE` | `DIRECTORY_SERVICE_BASE_URL` is empty or the Directory Service is asleep or down |
| Browser shows a CORS error | Add the frontend's exact origin (scheme + host, no trailing slash) to `CORS_ALLOWED_ORIGINS`, or send the calls through the gateway |
