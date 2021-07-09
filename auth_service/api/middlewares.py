import time

from fastapi import FastAPI, Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import Response
from starlette.types import ASGIApp

from auth_service.context import REQUEST_ID
from auth_service.log import access_logger, app_logger
from auth_service.models.common import Error
from auth_service.response import server_error

SECURITY_HEADERS = {
    "Cache-Control": "no-cache, no-store",
    "Expires": "0",
    "Pragma": "no-cache",
    "Access-Control-Allow-Origin": "*",  # FIXME: set origins
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
}


class AccessMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started_at = time.perf_counter()
        response = await call_next(request)
        request_time = time.perf_counter() - started_at

        status_code = response.status_code

        access_logger.info(
            msg="",
            extra={
                "request_time": round(request_time, 4),
                "status_code": status_code,
                "requested_url": request.url,
                "method": request.method,
            },
        )
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp, request_id_header: str):
        self.request_id_header = request_id_header
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(self.request_id_header, "-")
        token = REQUEST_ID.set(request_id)
        response = await call_next(request)
        if request_id != "-":
            response.headers[self.request_id_header] = request_id
        REQUEST_ID.reset(token)
        return response


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as e:  # pylint: disable=W0703,W1203
            app_logger.exception(
                msg=f"Caught unhandled exception: {e!r}"
            )
            error = Error(
                error_key="server_error",
                error_message=(
                    f"Internal server error {e.__class__}"
                    f"while processing request {REQUEST_ID.get('-')}"
                )
            )
            return server_error([error])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response


def add_middlewares(app: FastAPI, request_id_header: str) -> None:
    # do not change order
    app.add_middleware(ExceptionHandlerMiddleware)
    app.add_middleware(AccessMiddleware)
    app.add_middleware(
        RequestIdMiddleware,
        request_id_header=request_id_header,
    )
    app.add_middleware(SecurityHeadersMiddleware)
