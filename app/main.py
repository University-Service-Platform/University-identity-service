from fastapi import FastAPI
from app.core.config import API_V1_PREFIX, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, register_request_logging
from app.routes.validation import router as validation_router
from app.routes.health import router as health_router
from app.routes.protected_example import router as protected_example_router
from app.routes.role_catalogue import router as role_catalogue_router
from app.routes.roles import router as roles_router
from app.routes.users import router as users_router

# The schema is managed by Alembic migrations (`alembic upgrade head`) and reference
# data by `python -m app.seed`; importing the app no longer touches the database.
configure_logging(get_settings().log_level)

app = FastAPI(
    title="University Identity & Auth Service",
    description="Identity microservice handling Users, Roles, Account Status, and Validation APIs.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

register_exception_handlers(app)
register_request_logging(app)

app.include_router(health_router)
app.include_router(validation_router)
app.include_router(protected_example_router)
app.include_router(roles_router)
app.include_router(users_router)

app.include_router(role_catalogue_router, prefix=API_V1_PREFIX)
