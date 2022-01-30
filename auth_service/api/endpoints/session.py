import asyncio
import typing as tp
from http import HTTPStatus
from uuid import UUID

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
from auth_service.db.service import DBService
from auth_service.log import app_logger
from auth_service.models.auth import Credentials, TokenBody, TokenPair
from auth_service.response import create_response
from auth_service.security import SecurityService

router = APIRouter()


async def _create_token_pair(
    security_service: SecurityService,
    db_service: DBService,
    session_id: UUID,
) -> TokenPair:
    access_string, access = security_service.make_access_token(session_id)
    refresh_string, refresh = security_service.make_refresh_token(session_id)
    await asyncio.gather(
        db_service.add_access_token(access),
        db_service.add_refresh_token(refresh),
    )
    return TokenPair(access_token=access_string, refresh_token=refresh_string)


@router.post(
    path="/auth/login",
    tags=["Session"],
    status_code=HTTPStatus.OK,
    response_model=TokenPair,
    responses={
        403: responses.credentials_invalid_or_email_not_confirmed,
        422: responses.unprocessable_entity,
    }
)
async def login(
    request: Request,
    credentials: Credentials,
) -> TokenPair:
    app_logger.info(f"Login with email {credentials.email}")
    db_service = get_db_service(request.app)
    security_service = get_security_service(request.app)

    try:
        user_id, hashed_password = await db_service.get_user_with_password(
            credentials.email
        )
    except UserNotExists:
        app_logger.info(f"User with email {credentials.email} not exists")

        try:
            hashed_nc_password = await db_service.get_newcomer_password(
                credentials.email
            )
        except UserNotExists:
            app_logger.info(f"Newcomer {credentials.email} not exists")
            raise ForbiddenException(error_key="credentials.invalid")

        if security_service.is_password_correct(
            credentials.password,
            hashed_nc_password,
        ):
            app_logger.info("Newcomer exists, email not confirmed")
            raise ForbiddenException(error_key="email.not_confirmed")

        app_logger.info("Newcomer exists, password invalid")
        raise ForbiddenException(error_key="credentials.invalid")

    if not security_service.is_password_correct(
        credentials.password,
        hashed_password,
    ):
        app_logger.info(f"Password for user {user_id} invalid")
        raise ForbiddenException(error_key="credentials.invalid")

    session_id = await db_service.create_session(user_id)
    tokens = await _create_token_pair(security_service, db_service, session_id)
    app_logger.info(f"Session {session_id} created for user {user_id}")
    return tokens


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
        app_logger.info("Token or session not exists")
        raise ForbiddenException()

    return create_response(status_code=HTTPStatus.OK)


@router.post(
    path="/auth/refresh",
    tags=["Session"],
    status_code=HTTPStatus.OK,
    response_model=TokenPair,
    responses={
        403: responses.forbidden,
        422: responses.unprocessable_entity,
    }
)
async def refresh_tokens(
    request: Request,
    refresh_token: TokenBody,
) -> TokenPair:
    security_service = get_security_service(request.app)
    hashed_token = security_service.hash_token_string(refresh_token.token)

    db_service = get_db_service(request.app)
    try:
        session_id = await db_service.drop_valid_refresh_token(hashed_token)
    except NotExists:
        app_logger.info("Token or session not exists")
        raise ForbiddenException()

    tokens = await _create_token_pair(security_service, db_service, session_id)
    app_logger.info(f"Generated new token pair for session {session_id}")
    return tokens
