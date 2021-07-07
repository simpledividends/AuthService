import typing as tp

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette import status
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from auth_service.log import app_logger
from auth_service.models.common import Error
from auth_service.response import create_response, server_error

from .exceptions import AppException
from ..context import REQUEST_ID


def exc_to_str(exc: Exception) -> str:
    return f"{exc!r}"


async def default_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    app_logger.error("Default error handler caught: " + exc_to_str(exc))
    error = Error(
        error_key=f"server_error",
        error_message=(
            f"Internal server error {exc.__class__} occurred"
            f"while processing request {REQUEST_ID.get('-')}"
        )
    )
    return server_error([error])


async def http_error_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    log_msg = "HTTP error: " + exc_to_str(exc)
    if exc.status_code >= 500:
        app_logger.error(log_msg)
    else:
        app_logger.info(log_msg)
    error = Error(error_key="http_exception", error_message=exc.detail)
    return create_response(status_code=exc.status_code, errors=[error])


async def validation_error_handler(
        request: Request,
        exc: tp.Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    errors = [
        Error(
            error_key=err.get("type"),
            error_message=err.get("msg"),
            error_loc=err.get("loc"),
        )
        for err in exc.errors()
    ]
    app_logger.info("Validation errors: " + str(errors))
    return create_response(status.HTTP_422_UNPROCESSABLE_ENTITY, errors=errors)


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    errors = [
        Error(
            error_key=exc.error_key,
            error_message=exc.error_message,
            error_loc=exc.error_loc,
        )
    ]
    log_msg = "Application errors: " + str(errors)
    if exc.status_code >= 500:
        app_logger.error(log_msg)
    else:
        app_logger.info(log_msg)
    return create_response(exc.status_code, errors=errors)


def add_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, default_error_handler)
