from fastapi import FastAPI
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, register_request_logging
from app.database import engine, Base, SessionLocal
from app.models.role import Role
from app.routes.validation import router as validation_router
from app.routes.health import router as health_router
from app.routes.protected_example import router as protected_example_router
from app.routes.roles import router as roles_router
from app.routes.users import router as users_router

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        default_roles = [
            ("ADMIN", "Administrator Role"),
            ("STAFF", "Staff Member Role"),
            ("STUDENT", "Student Role")
        ]
        for role_name, description in default_roles:
            existing = db.query(Role).filter(Role.name == role_name).first()
            if not existing:
                db.add(Role(name=role_name, description=description))
        db.commit()
    finally:
        db.close()

init_db()

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
