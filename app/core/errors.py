import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("identity.errors")

# Default error codes for HTTP errors raised without an explicit service error code
DEFAULT_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_SERVER_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def error_body(code: str, message: str, details: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    The single error envelope used by every endpoint:
    {"success": false, "error": {"code", "message", ["details"]}, "timestamp"}
    """
    error: Dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"success": False, "error": error, "timestamp": _timestamp()}


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    headers = getattr(exc, "headers", None)

    # Service errors already carry the standard envelope; keep their code and message.
    if isinstance(exc.detail, dict) and "success" in exc.detail:
        error = exc.detail.get("error", {})
        content = error_body(
            code=error.get("code", DEFAULT_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")),
            message=error.get("message", ""),
            details=error.get("details"),
        )
        return JSONResponse(status_code=exc.status_code, content=content, headers=headers)

    content = error_body(
        code=DEFAULT_ERROR_CODES.get(exc.status_code, "HTTP_ERROR"),
        message=str(exc.detail),
    )
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in err.get("loc", [])),
            "message": err.get("msg", "Invalid value."),
            "type": err.get("type", "value_error"),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", "Request validation failed.", details),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full error server-side; never expose internal details to clients.
    logger.exception(
        "Unhandled error on %s %s (request_id=%s)",
        request.method,
        request.url.path,
        getattr(request.state, "request_id", "-"),
    )
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_SERVER_ERROR", "An unexpected error occurred. Please try again later."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
