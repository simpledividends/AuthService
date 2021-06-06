from http import HTTPStatus

from fastapi import APIRouter, FastAPI, Request
from starlette.responses import JSONResponse

from auth_service.response import create_response


async def ping(_: Request) -> JSONResponse:
    return create_response(message="pong", status_code=HTTPStatus.OK)


def add_routes(app: FastAPI) -> None:
    router = APIRouter()

    router.add_route(
        path="/ping",
        endpoint=ping,
        methods=["GET"],
    )

    app.include_router(router)
