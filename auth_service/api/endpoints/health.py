from http import HTTPStatus

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from auth_service.api.services import get_db_service
from auth_service.response import create_response

router = APIRouter()


@router.get(
    path="/ping",
    tags=["Health"],
)
async def ping(_: Request) -> JSONResponse:
    return create_response(message="pong!", status_code=HTTPStatus.OK)


@router.get(
    path="/health",
    tags=["Health"],
)
async def health(request: Request) -> JSONResponse:
    await get_db_service(request.app).ping()
    return create_response(status_code=HTTPStatus.OK)
