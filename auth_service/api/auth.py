import typing as tp

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from auth_service.db.exceptions import UserNotExists
from auth_service.log import app_logger
from auth_service.models.user import User, UserRole

from .exceptions import ForbiddenException, NotFoundException
from .services import get_db_service, get_security_service

AUTHORIZATION_HEADER = "Authorization"
BEARER_SCHEME = "Bearer"


auth_api_key_header = APIKeyHeader(
    name=AUTHORIZATION_HEADER,
    auto_error=False,
)


def extract_token_from_header(header: tp.Optional[str]) -> str:
    if not header:
        app_logger.info("Authorization header not recognized")
        raise ForbiddenException(
            error_key="authorization.not_set",
            error_message="Authorization header not recognized"
        )

    try:
        scheme, token = header.split()
    except ValueError:
        app_logger.info("Authorization scheme not recognized")
        raise ForbiddenException(
            error_key="authorization.scheme_unrecognised",
            error_message="Authorization scheme not recognised"
        )

    if scheme != BEARER_SCHEME:
        app_logger.info("Authorization scheme invalid")
        raise ForbiddenException(
            error_key="authorization.scheme_invalid",
            error_message="Expected Bearer authorization scheme"
        )

    return token


async def get_request_user(
    request: Request,
    header: tp.Optional[str] = Security(auth_api_key_header),
) -> User:
    token = extract_token_from_header(header)

    security_service = get_security_service(request.app)
    hashed_token = security_service.hash_token_string(token)

    db_service = get_db_service(request.app)

    try:
        user = await db_service.get_user_by_access_token(hashed_token)
    except UserNotExists:
        app_logger.info("Access token invalid")
        raise ForbiddenException()

    app_logger.info(f"Request from user {user.user_id}")
    return user


async def get_request_admin(
    request: Request,
    header: tp.Optional[str] = Security(auth_api_key_header),
) -> User:
    try:
        user = await get_request_user(request, header)
    except ForbiddenException:
        raise NotFoundException()

    if user.role != UserRole.admin:
        app_logger.info(f"User {user.user_id} is not admin")
        raise NotFoundException()

    return user
