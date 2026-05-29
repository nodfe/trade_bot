"""Unified API error envelope and exception handlers.

All HTTP responses on the error path go through this module so that
admin, bot, and any future client see the same shape:

    {
      "error": {
        "code": "NOT_FOUND",
        "message": "No stock found for 600519",
        "details": null
      },
      "request_id": "8f1c2d6e-...".
    }

Routes raise:
- ``app.core.exceptions.AppException`` and subclasses (NotFoundError, ...) for
  expected, user-visible errors. They map 1:1 to a response code.
- Anything else (uncaught ``Exception``) becomes ``INTERNAL_ERROR`` with a
  500 status; the original traceback is logged but not leaked to the client.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AppException,
    BadRequestError,
    ExternalAPIError,
    NotFoundError,
    UnauthorizedError,
)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
    request_id: str | None = None


# Map known exception classes to short, stable error codes. Adding a new
# AppException subclass without registering it here results in a generic
# "APP_ERROR" code, which is acceptable but worth tightening over time.
_CODE_BY_CLASS: dict[type[AppException], str] = {
    NotFoundError: "NOT_FOUND",
    BadRequestError: "BAD_REQUEST",
    UnauthorizedError: "UNAUTHORIZED",
    ExternalAPIError: "EXTERNAL_API_ERROR",
}


def _envelope(
    *,
    code: str,
    message: str,
    status_code: int,
    request: Request,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, details=details),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers={"X-Request-ID": request_id} if request_id else None,
    )


async def _handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    code = _CODE_BY_CLASS.get(type(exc), "APP_ERROR")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    logger.warning(f"AppException {code} ({exc.status_code}): {detail}")
    return _envelope(
        code=code,
        message=detail,
        status_code=exc.status_code,
        request=request,
    )


async def _handle_starlette_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    # FastAPI raises StarletteHTTPException for things like 404 on unknown
    # routes. Wrap them in the same envelope.
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _envelope(
        code="HTTP_ERROR",
        message=detail,
        status_code=exc.status_code,
        request=request,
    )


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _envelope(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        request=request,
        details={"errors": exc.errors()},
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return _envelope(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request=request,
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register exception handlers on the FastAPI app."""
    app.add_exception_handler(AppException, _handle_app_exception)
    app.add_exception_handler(StarletteHTTPException, _handle_starlette_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected)
