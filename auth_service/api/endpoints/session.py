import asyncio
from http import HTTPStatus

from fastapi import APIRouter, Request

from auth_service.api.endpoints import responses
from auth_service.api.exceptions import ForbiddenException
from auth_service.api.services import get_security_service, get_db_service
from auth_service.db.exceptions import UserNotExists
from auth_service.models.auth import Credentials, TokenPair

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
        raise ForbiddenException()

    security_service = get_security_service(request.app)
    if not security_service.is_password_correct(
        credentials.password,
        hashed_password,
    ):
        raise ForbiddenException()

    session_id = await db_service.create_session(user_id)
    access_string, access = security_service.make_access_token(session_id)
    refresh_string, refresh = security_service.make_refresh_token(session_id)
    await asyncio.gather(
        db_service.add_access_token(access),
        db_service.add_refresh_token(refresh),
    )
    return TokenPair(access_token=access_string, refresh_token=refresh_string)
