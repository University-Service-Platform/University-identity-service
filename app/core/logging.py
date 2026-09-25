import logging
import time
import uuid

from fastapi import FastAPI, Request

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger("identity.requests")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def register_request_logging(app: FastAPI) -> None:
    """
    Log one line per request (method, path, status, duration) and propagate a request ID.
    An incoming X-Request-ID (e.g. set by the API Gateway) is reused so a request can be
    traced across services; otherwise a new one is generated.
    """

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.error(
                "%s %s -> 500 (%.1f ms) request_id=%s",
                request.method, request.url.path, duration_ms, request_id,
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s -> %s (%.1f ms) request_id=%s",
            request.method, request.url.path, response.status_code, duration_ms, request_id,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
