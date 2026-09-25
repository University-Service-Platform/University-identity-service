from fastapi import Depends, FastAPI
from app.core.config import API_V1_PREFIX, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, register_request_logging
from app.core.security import get_signing_keys
from app.routes.audit import router as audit_router
from app.routes.auth import jwks_router, router as auth_router
from app.routes.deprecation import LEGACY_TAG, legacy_route
from app.routes.validation import router as legacy_validation_router, v1_router as validation_router
from app.routes.health import router as health_router
from app.routes.protected_example import router as protected_example_router
from app.routes.role_catalogue import router as role_catalogue_router
from app.routes.roles import router as roles_router
from app.routes.users import router as users_router

# The schema is managed by Alembic migrations (`alembic upgrade head`) and reference
# data by `python -m app.seed`; importing the app no longer touches the database.
configure_logging(get_settings().log_level)
# Load (or, in development, generate) the JWT signing keys at startup so a
# misconfigured key path fails fast instead of on the first login.
get_signing_keys()

app = FastAPI(
    title="University Identity & Auth Service",
    description="Identity microservice handling Users, Roles, Account Status, and Validation APIs.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

register_exception_handlers(app)
register_request_logging(app)

# Unversioned infrastructure endpoints
app.include_router(health_router)
app.include_router(jwks_router)

# Versioned API: the stable contract for other services, the frontend and the API Gateway
for v1_router in (auth_router, users_router, roles_router, role_catalogue_router, validation_router, audit_router):
    app.include_router(v1_router, prefix=API_V1_PREFIX)

# Sprint 1 unversioned routes, kept as deprecated aliases so existing consumers keep working.
# Responses carry "Deprecation: true" and a Link header pointing at the successor.
for legacy_router in (users_router, roles_router, legacy_validation_router):
    app.include_router(legacy_router, deprecated=True, tags=[LEGACY_TAG],
                       dependencies=[Depends(legacy_route())])
app.include_router(protected_example_router, deprecated=True, tags=[LEGACY_TAG],
                   dependencies=[Depends(legacy_route(f"{API_V1_PREFIX}/auth/me"))])
