"""ASGI middleware that assigns a request ID per request.

Every incoming request gets a UUID4 (or honors an inbound ``X-Request-ID``
header for cross-service tracing). The ID is:

- stored on ``request.state.request_id`` so error handlers can echo it
- bound into the loguru context so every log line during the request
  carries ``request_id={...}``
- echoed back as ``X-Request-ID`` on the response

Cheap to compute, makes oncall and admin sync-status work meaningful.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id

        with logger.contextualize(request_id=request_id):
            response = await call_next(request)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
