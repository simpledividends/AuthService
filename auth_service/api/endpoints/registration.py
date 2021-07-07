from http import HTTPStatus
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.background import BackgroundTasks
from starlette.responses import JSONResponse

from auth_service.api import responses
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
    TokenNotFound,
    TooManyChangeSameEmailRequests,
    TooManyNewcomersWithSameEmail,
    UserAlreadyExists,
)
from auth_service.log import app_logger
from auth_service.models.auth import TokenBody
from auth_service.models.user import (
    Newcomer,
    NewcomerFull,
    NewcomerRegistered,
    User,
)
from auth_service.response import create_response
from auth_service.utils import utc_now

router = APIRouter()


@router.post(
    path="/auth/register",
    tags=["Registration"],
    status_code=HTTPStatus.CREATED,
    response_model=Newcomer,
    responses={
        409: responses.conflict_or_email_exists,
        422: responses.unprocessable_entity_or_password_improper,
    }
)
async def register(
    request: Request,
    newcomer: NewcomerRegistered,
    background_tasks: BackgroundTasks,
) -> Newcomer:
    app_logger.info(
        f"Registration with email {newcomer.email} and name {newcomer.name}"
    )

    security_service = get_security_service(request.app)
    if not security_service.is_password_proper(newcomer.password):
        app_logger.info(f"Password is improper")
        raise ImproperPasswordError()

    newcomer_full = NewcomerFull(
        name=newcomer.name,
        email=newcomer.email,
        hashed_password=security_service.hash_password(newcomer.password),
        user_id=uuid4(),
        created_at=utc_now(),
    )
    token_string, token = security_service.make_registration_token(
        newcomer_full.user_id,
    )

    db_service = get_db_service(request.app)
    try:
        created = await db_service.create_newcomer(newcomer_full, token)
    except UserAlreadyExists:
        app_logger.info(f"User with email {newcomer.email} is already exists")
        raise UserConflictException(
            error_key="email.already_exists",
            error_message="User with given email is already exists",
        )
    except TooManyNewcomersWithSameEmail:
        app_logger.info(f"Too many newcomers with email {newcomer.email}")
        raise UserConflictException()
    except TooManyChangeSameEmailRequests:
        app_logger.info(f"Too many changes email {newcomer.email}")
        raise UserConflictException()

    app_logger.info(f"Created newcomer {created.user_id}")

    mail_service = get_mail_service(request.app)
    background_tasks.add_task(
        mail_service.send_registration_letter,
        newcomer=created,
        token=token_string,
    )
    return created


@router.post(
    path="/auth/register/verify",
    tags=["Registration"],
    status_code=HTTPStatus.OK,
    responses={
        403: responses.forbidden,
        409: responses.conflict_email_exists,
        422: responses.unprocessable_entity,
    }
)
async def verify_registered_user(
    request: Request,
    verification: TokenBody,
) -> JSONResponse:
    security_service = get_security_service(request.app)
    hashed_token = security_service.hash_token_string(verification.token)

    db_service = get_db_service(request.app)
    try:
        await db_service.verify_newcomer(hashed_token)
    except TokenNotFound:
        app_logger.info("Token not found")
        raise ForbiddenException()
    except UserAlreadyExists:
        app_logger.info("User with same email already exists")
        raise UserConflictException(
            error_key="email.already_exists",
            error_message="User with this email already exists",
        )

    app_logger.info(f"Verified user {user.user_id}")
    return create_response(status_code=HTTPStatus.OK)
