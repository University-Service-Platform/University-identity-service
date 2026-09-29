from typing import Callable, Optional

from fastapi import Request, Response

from app.core.config import API_V1_PREFIX

LEGACY_TAG = "Legacy (deprecated, use /api/v1)"


def legacy_route(successor: Optional[str] = None) -> Callable[[Request, Response], None]:
    """
    Dependency for the unversioned Sprint 1 aliases: signals deprecation to clients
    (RFC 8594 style) and points at the successor endpoint, by default the same path
    under /api/v1. Behind the API Gateway the link keeps the gateway prefix (root_path).
    """
    def mark(request: Request, response: Response) -> None:
        response.headers["Deprecation"] = "true"
        root_path = request.scope.get("root_path", "")
        # Depending on the server, scope["path"] may or may not already include root_path
        path = request.scope["path"]
        if root_path and path.startswith(root_path):
            path = path[len(root_path):]
        target = successor or f"{API_V1_PREFIX}{path}"
        response.headers["Link"] = f'<{root_path}{target}>; rel="successor-version"'
    return mark
