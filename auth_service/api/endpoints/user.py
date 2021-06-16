from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from auth_service.api import responses
from auth_service.api.auth import get_request_user
from auth_service.api.exceptions import (
    ForbiddenException,
    ImproperPasswordError,
    NotFoundException,
)
from auth_service.api.services import get_db_service, get_security_service
from auth_service.db.exceptions import PasswordInvalid, UserNotExists
from auth_service.models.user import PasswordPair, User, UserInfo, UserRole
from auth_service.response import create_response

router = APIRouter()


@router.get(
    path="/auth/users/me",
    tags=["User"],
    status_code=HTTPStatus.OK,
    response_model=User,
    responses={
        403: responses.forbidden,
    }
)
def get_me(
    user: User = Depends(get_request_user),
) -> User:
    return user


@router.patch(
    path="/auth/users/me",
    tags=["User"],
    status_code=HTTPStatus.OK,
    response_model=User,
    responses={
        403: responses.forbidden,
        422: responses.unprocessable_entity,
    }
)
async def patch_me(
    request: Request,
    new_user_info: UserInfo,
    user: User = Depends(get_request_user),
) -> User:
    db_service = get_db_service(request.app)
    updated_user = await db_service.update_user(user.user_id, new_user_info)
    return updated_user


@router.patch(
    path="/auth/users/me/password",
    tags=["User"],
    status_code=HTTPStatus.OK,
    responses={
        403: responses.forbidden_or_password_invalid,
        422: responses.unprocessable_entity_or_password_improper,
    }
)
async def patch_my_password(
    request: Request,
    password_pair: PasswordPair,
    user: User = Depends(get_request_user),
) -> JSONResponse:
    security_service = get_security_service(request.app)
    if not security_service.is_password_proper(password_pair.new_password):
        raise ImproperPasswordError()

    db_service = get_db_service(request.app)
    try:
        await db_service.update_password_if_old_is_valid(
            user.user_id,
            security_service.hash_password(password_pair.new_password),
            lambda pass_hash: security_service.is_password_correct(
                password_pair.password,
                pass_hash,
            )
        )
    except PasswordInvalid:
        raise ForbiddenException(error_key="password.invalid")

    return create_response(status_code=HTTPStatus.OK)


@router.get(
    path="/auth/users/{user_id}",
    tags=["User"],
    status_code=HTTPStatus.OK,
    response_model=User,
    responses={
        403: responses.forbidden,
        404: responses.not_found,
        422: responses.unprocessable_entity,
    }
)
async def get_user(
    request: Request,
    user_id: UUID,
    user: User = Depends(get_request_user),
) -> User:
    if user.role != UserRole.admin:
        raise NotFoundException()

    db_service = get_db_service(request.app)
    try:
        user = await db_service.get_user(user_id)
    except UserNotExists:
        raise NotFoundException()

    return user
