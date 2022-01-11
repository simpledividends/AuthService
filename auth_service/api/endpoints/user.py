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
from auth_service.log import app_logger
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
    app_logger.info(f"User {user.user_id} requested itself")
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
    app_logger.info(
        f"User {user.user_id} with name {user.name} "
        f"changes name to {new_user_info.name}"
    )
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
    app_logger.info(f"User {user.user_id} changes password")
    security_service = get_security_service(request.app)
    if not security_service.is_password_proper(password_pair.new_password):
        app_logger.info("New password is improper")
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
        app_logger.info("Old password is invalid")
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
    app_logger.info(
        f"User {user.user_id} with email {user.email} "
        f"changes email to {data.new_email}"
    )
    db_service = get_db_service(request.app)
    security_service = get_security_service(request.app)

    _, hashed_pass = await db_service.get_user_with_password(user.email)
    if not security_service.is_password_correct(data.password, hashed_pass):
        app_logger.info("Password is invalid")
        raise ForbiddenException(error_key="password.invalid")

    token_string, token = security_service.make_change_email_token(
        user.user_id,
        data.new_email,
    )
    try:
        await db_service.add_change_email_token(token)
    except UserAlreadyExists:
        app_logger.info(f"User with email {data.new_email} is already exists")
        raise UserConflictException(
            error_key="email.already_exists",
            error_message="User with given email is already exists",
        )
    except TooManyNewcomersWithSameEmail:
        app_logger.info(f"Too many newcomers with email {data.new_email}")
        raise UserConflictException()
    except TooManyChangeSameEmailRequests:
        app_logger.info(f"Too many changes email {data.new_email}")
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
        user = await db_service.verify_email(hashed_token)
    except TokenNotFound:
        app_logger.info("Token not found")
        raise ForbiddenException()
    except UserAlreadyExists:
        app_logger.info("User with same email already exists")
        raise UserConflictException(
            error_key="email.already_exists",
            error_message="User with this email is already exists",
        )

    app_logger.info(f"Verified new email {user.email} for user {user.user_id}")
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
    app_logger.info(f"Forgot password request for email {email_body.email}")

    response = create_response(status_code=HTTPStatus.ACCEPTED)
    db_service = get_db_service(request.app)
    try:
        user = await db_service.get_user_by_email(email_body.email)
    except UserNotExists:
        app_logger.info(f"User with email {email_body.email} not exists")
        return response

    security_service = get_security_service(request.app)
    token_string, token = security_service.make_password_token(user.user_id)

    try:
        await db_service.create_password_token(token)
    except UserNotExists:
        app_logger.info(f"User with email {email_body.email} not exists (2)")
    except TooManyPasswordTokens:
        app_logger.info(
            f"Too many password tokens for user with email {email_body.email}"
        )
        return response

    app_logger.info(
        f"Created password token for user with email {email_body.email}"
    )

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
        app_logger.info("Improper new password")
        raise ImproperPasswordError()

    hashed_token = security_service.hash_token_string(verification.token)

    db_service = get_db_service(request.app)
    try:
        await db_service.update_password_by_token(
            hashed_token,
            security_service.hash_password(verification.password),
        )
    except TokenNotFound:
        app_logger.info("Token not found")
        raise ForbiddenException()

    return create_response(status_code=HTTPStatus.OK)
