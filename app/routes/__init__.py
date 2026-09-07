from app.routes.validation import router as validation_router
from app.routes.health import router as health_router
from app.routes.protected_example import router as protected_example_router

__all__ = ["validation_router", "health_router", "protected_example_router"]
