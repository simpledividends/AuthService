import typing as tp

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from auth_service.api.exceptions import ForbiddenException
from auth_service.api.services import get_db_service, get_security_service
from auth_service.db.exceptions import UserNotExists
from auth_service.models.user import User

AUTHORIZATION_HEADER = "Authorization"
BEARER_SCHEME = "Bearer"


auth_api_key_header = APIKeyHeader(
    name=AUTHORIZATION_HEADER,
    auto_error=False,
)


def extract_token_from_header(header: tp.Optional[str]) -> str:
    if not header:
        raise ForbiddenException(
            error_key="authorization.not_set",
            error_message="Authorization header not recognized"
        )

    try:
        scheme, token = header.split()
    except ValueError:
        raise ForbiddenException(
            error_key="authorization.scheme_unrecognised",
            error_message="Authorization scheme not recognised"
        )

    if scheme != BEARER_SCHEME:
        raise ForbiddenException(
            error_key="authorization.scheme_invalid",
            error_message="Expected Bearer authorization scheme"
        )

    return token


async def get_request_user(
    request: Request,
    header: tp.Optional[str] = Security(auth_api_key_header)
) -> User:
    token = extract_token_from_header(header)

    security_service = get_security_service(request.app)
    hashed_token = security_service.hash_token_string(token)

    db_service = get_db_service(request.app)

    try:
        user = await db_service.get_user_by_access_token(hashed_token)
    except UserNotExists:
        raise ForbiddenException()

    return user
