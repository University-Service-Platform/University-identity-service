from typing import Callable, Optional

from fastapi import Request, Response

from app.core.config import API_V1_PREFIX

LEGACY_TAG = "Legacy (deprecated, use /api/v1)"


def legacy_route(successor: Optional[str] = None) -> Callable[[Request, Response], None]:
    """
    Dependency for the unversioned Sprint 1 aliases: signals deprecation to clients
    (RFC 8594 style) and points at the successor endpoint, by default the same path
    under /api/v1.
    """
    def mark(request: Request, response: Response) -> None:
        response.headers["Deprecation"] = "true"
        target = successor or f"{API_V1_PREFIX}{request.url.path}"
        response.headers["Link"] = f'<{target}>; rel="successor-version"'
    return mark
