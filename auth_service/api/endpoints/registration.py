from http import HTTPStatus

from fastapi import APIRouter, Request
from starlette.background import BackgroundTasks

from auth_service.api import responses
from auth_service.api.exceptions import (
    ForbiddenException,
    InvalidPasswordError,
    UserConflictException,
)
from auth_service.api.services import (
    get_db_service,
    get_mail_service,
    get_security_service,
)
from auth_service.db.exceptions import (
    TokenNotFound,
    TooManyNewcomersWithSameEmail,
    UserAlreadyExists,
)
from auth_service.db.service import DBService
from auth_service.mail.service import MailService
from auth_service.models.auth import VerificationRequest
from auth_service.models.user import Newcomer, NewcomerRegistered, User
from auth_service.security import SecurityService

router = APIRouter()


async def make_registration_mail(
    newcomer: Newcomer,
    db_service: DBService,
    security_service: SecurityService,
    mail_service: MailService,
) -> None:
    token_string, token = security_service.make_registration_token(
        newcomer.user_id,
    )
    await db_service.save_registration_token(token)
    await mail_service.send_registration_letter(newcomer, token_string)


@router.post(
    path="/auth/register",
    tags=["Registration"],
    status_code=HTTPStatus.CREATED,
    response_model=Newcomer,
    responses={
        409: responses.conflict_register,
        422: responses.unprocessable_entity_or_password_invalid,
    }
)
async def register(
    request: Request,
    newcomer: NewcomerRegistered,
    background_tasks: BackgroundTasks,
) -> Newcomer:
    security_service = get_security_service(request.app)
    if not security_service.is_password_valid(newcomer.password):
        raise InvalidPasswordError()

    db_service = get_db_service(request.app)
    newcomer = newcomer.copy(
        update={"password": security_service.hash_password(newcomer.password)}
    )
    try:
        newcomer_created = await db_service.create_newcomer(newcomer)
    except UserAlreadyExists:
        raise UserConflictException(
            error_key="email.already_exists",
            error_message="User with given email is already exists",
        )
    except TooManyNewcomersWithSameEmail:
        raise UserConflictException()

    background_tasks.add_task(
        make_registration_mail,
        newcomer=newcomer_created,
        db_service=db_service,
        security_service=security_service,
        mail_service=get_mail_service(request.app),
    )
    return newcomer_created


@router.post(
    path="/auth/register/verify",
    tags=["Registration"],
    status_code=HTTPStatus.OK,
    response_model=User,
    responses={
        403: responses.forbidden,
        409: responses.conflict_register_verify,
        422: responses.unprocessable_entity,
    }
)
async def verify_registered_user(
    request: Request,
    verification: VerificationRequest,
) -> User:
    security_service = get_security_service(request.app)
    hashed_token = security_service.hash_token_string(verification.token)

    db_service = get_db_service(request.app)
    try:
        user = await db_service.verify_newcomer(hashed_token)
    except TokenNotFound:
        raise ForbiddenException()
    except UserAlreadyExists:
        raise UserConflictException(
            error_key="email.already_verified",
            error_message="User with this email is already exists",
        )

    return user
