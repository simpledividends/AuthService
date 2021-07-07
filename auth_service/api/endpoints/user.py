from http import HTTPStatus

from fastapi import APIRouter, Depends, Request
from starlette.background import BackgroundTasks
from starlette.responses import JSONResponse

from auth_service.api import responses
from auth_service.api.auth import get_request_user
from auth_service.api.exceptions import (
    ForbiddenException,
    ImproperPasswordError,
    UserConflictException,
)
from auth_service.api.services import (
    get_db_service,
    get_mail_service,
    get_security_service,
)
from auth_service.db.exceptions import (
    PasswordInvalid,
    TokenNotFound,
    TooManyChangeSameEmailRequests,
    TooManyNewcomersWithSameEmail,
    TooManyPasswordTokens,
    UserAlreadyExists,
    UserNotExists,
)
from auth_service.models.auth import EmailBody, TokenBody, TokenPasswordBody
from auth_service.models.user import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    User,
    UserInfo,
)
from auth_service.response import create_response

router = APIRouter()


@router.get(
    path="/users/me",
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
    path="/users/me",
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
    path="/users/me/password",
    tags=["User"],
    status_code=HTTPStatus.OK,
    responses={
        403: responses.forbidden_or_password_invalid,
        422: responses.unprocessable_entity_or_password_improper,
    }
)
async def patch_my_password(
    request: Request,
    password_pair: ChangePasswordRequest,
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


@router.patch(
    path="/users/me/email",
    tags=["User"],
    status_code=HTTPStatus.OK,
    responses={
        403: responses.forbidden_or_password_invalid,
        409: responses.conflict_or_email_exists,
        422: responses.unprocessable_entity,
    }
)
async def patch_my_email(
    request: Request,
    background_tasks: BackgroundTasks,
    data: ChangeEmailRequest,
    user: User = Depends(get_request_user),
) -> JSONResponse:
    db_service = get_db_service(request.app)
    security_service = get_security_service(request.app)

    _, hashed_pass = await db_service.get_user_with_password(user.email)
    if not security_service.is_password_correct(data.password, hashed_pass):
        raise ForbiddenException(error_key="password.invalid")

    token_string, token = security_service.make_change_email_token(
        user.user_id,
        data.new_email,
    )
    try:
        await db_service.add_change_email_token(token)
    except UserAlreadyExists:
        raise UserConflictException(
            error_key="email.already_exists",
            error_message="User with given email is already exists",
        )
    except (TooManyNewcomersWithSameEmail, TooManyChangeSameEmailRequests):
        raise UserConflictException()

    mail_service = get_mail_service(request.app)
    background_tasks.add_task(
        mail_service.send_change_email_letter,
        user=user,
        new_email=data.new_email,
        token=token_string,
    )
    return create_response(status_code=HTTPStatus.OK)


@router.post(
    path="/users/me/email/verify",
    tags=["User"],
    status_code=HTTPStatus.OK,
    responses={
        403: responses.forbidden,
        409: responses.conflict_email_exists,
        422: responses.unprocessable_entity,
    }
)
async def verify_email_change(
    request: Request,
    verification: TokenBody,
) -> JSONResponse:
    security_service = get_security_service(request.app)
    hashed_token = security_service.hash_token_string(verification.token)

    db_service = get_db_service(request.app)
    try:
        _ = await db_service.verify_email(hashed_token)
    except TokenNotFound:
        raise ForbiddenException()
    except UserAlreadyExists:
        raise UserConflictException(
            error_key="email.already_exists",
            error_message="User with this email is already exists",
        )

    return create_response(status_code=HTTPStatus.OK)


@router.post(
    path="/users/me/password/forgot",
    tags=["User"],
    status_code=HTTPStatus.ACCEPTED,
    responses={
        422: responses.unprocessable_entity,
    }
)
async def forgot_password(
    request: Request,
    email_body: EmailBody,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    response = create_response(status_code=HTTPStatus.ACCEPTED)
    db_service = get_db_service(request.app)
    try:
        user = await db_service.get_user_by_email(email_body.email)
    except UserNotExists:
        return response

    security_service = get_security_service(request.app)
    token_string, token = security_service.make_password_token(user.user_id)

    try:
        await db_service.create_password_token(token)
    except (UserNotExists, TooManyPasswordTokens):
        return response

    mail_service = get_mail_service(request.app)
    background_tasks.add_task(
        mail_service.send_forgot_password_letter,
        user=user,
        token=token_string,
    )
    return response


@router.post(
    path="/users/me/password/reset",
    tags=["User"],
    status_code=HTTPStatus.OK,
    responses={
        403: responses.forbidden,
        422: responses.unprocessable_entity_or_password_improper,
    }
)
async def reset_password(
    request: Request,
    verification: TokenPasswordBody,
) -> JSONResponse:
    security_service = get_security_service(request.app)
    if not security_service.is_password_proper(verification.password):
        raise ImproperPasswordError()

    hashed_token = security_service.hash_token_string(verification.token)

    db_service = get_db_service(request.app)
    try:
        await db_service.update_password_by_token(
            hashed_token,
            security_service.hash_password(verification.password),
        )
    except TokenNotFound:
        raise ForbiddenException()

    return create_response(status_code=HTTPStatus.OK)
