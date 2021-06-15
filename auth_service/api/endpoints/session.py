import asyncio
import typing as tp
from http import HTTPStatus

from fastapi import APIRouter, Request, Security
from starlette.responses import JSONResponse

from auth_service.api import responses
from auth_service.api.auth import (
    auth_api_key_header,
    extract_token_from_header,
)
from auth_service.api.exceptions import ForbiddenException
from auth_service.api.services import get_db_service, get_security_service
from auth_service.db.exceptions import NotExists, UserNotExists
from auth_service.models.auth import Credentials, TokenPair
from auth_service.response import create_response

router = APIRouter()


@router.post(
    path="/auth/login",
    tags=["Session"],
    status_code=HTTPStatus.OK,
    response_model=TokenPair,
    responses={
        403: responses.forbidden,
        422: responses.unprocessable_entity,
    }
)
async def login(
    request: Request,
    credentials: Credentials,
) -> TokenPair:
    db_service = get_db_service(request.app)
    try:
        user_id, hashed_password = await db_service.get_user_with_password(
            credentials.email
        )
    except UserNotExists:
        raise ForbiddenException(error_key="credentials.invalid")

    security_service = get_security_service(request.app)
    if not security_service.is_password_correct(
        credentials.password,
        hashed_password,
    ):
        raise ForbiddenException(error_key="credentials.invalid")

    session_id = await db_service.create_session(user_id)
    access_string, access = security_service.make_access_token(session_id)
    refresh_string, refresh = security_service.make_refresh_token(session_id)
    await asyncio.gather(
        db_service.add_access_token(access),
        db_service.add_refresh_token(refresh),
    )
    return TokenPair(access_token=access_string, refresh_token=refresh_string)


@router.post(
    path="/auth/logout",
    tags=["Session"],
    status_code=HTTPStatus.OK,
    responses={
        403: responses.forbidden,
    }
)
async def logout(
    request: Request,
    header: tp.Optional[str] = Security(auth_api_key_header)
) -> JSONResponse:
    token = extract_token_from_header(header)

    security_service = get_security_service(request.app)
    hashed_token = security_service.hash_token_string(token)

    db_service = get_db_service(request.app)
    try:
        await db_service.finish_session(hashed_token)
    except NotExists:
        raise ForbiddenException()

    return create_response(status_code=HTTPStatus.OK)
