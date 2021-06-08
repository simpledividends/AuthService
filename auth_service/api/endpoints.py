from http import HTTPStatus

from fastapi import APIRouter, FastAPI, Request
from starlette.responses import JSONResponse

from auth_service.response import create_response

router = APIRouter()


@router.get(
    path="/ping",
)
async def ping(_: Request) -> JSONResponse:
    return create_response(message="pong", status_code=HTTPStatus.OK)


@router.post(
    path="/auth/register"
)
async def register() -> User:


def add_routes(app: FastAPI) -> None:
    app.include_router(router)
