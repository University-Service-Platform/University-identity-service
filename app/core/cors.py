from typing import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Clients authenticate with a Bearer header, not cookies, so credentials stay disabled.
ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = ["Authorization", "Content-Type", "X-Request-ID"]
# Response headers the browser may read: tracing and deprecation notices
EXPOSED_HEADERS = ["X-Request-ID", "Deprecation", "Link"]


def register_cors(app: FastAPI, allowed_origins: Sequence[str]) -> None:
    """
    Allow the listed browser origins (e.g. the shared frontend) to call the service directly.
    With no origins configured nothing is registered, which suits gateway-only access.
    Must be registered after other middleware so it is outermost and error responses
    also carry CORS headers.
    """
    if not allowed_origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
        expose_headers=EXPOSED_HEADERS,
    )
