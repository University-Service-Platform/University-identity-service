from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
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

app = FastAPI(
    title="University Identity & Auth Service",
    description="Identity microservice handling Users, Roles, Account Status, and Validation APIs.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "success" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    
    code = "HTTP_ERROR"
    if exc.status_code == 400:
        code = "BAD_REQUEST"
    elif exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 409:
        code = "CONFLICT"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": str(exc.detail)
            }
        }
    )

app.include_router(health_router)
app.include_router(validation_router)
app.include_router(protected_example_router)
app.include_router(roles_router)
app.include_router(users_router)
