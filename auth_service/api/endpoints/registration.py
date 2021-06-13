from http import HTTPStatus

from fastapi import APIRouter, Request
from starlette.background import BackgroundTasks

from auth_service.api.endpoints import responses
from auth_service.api.exceptions import (
    InvalidPasswordError,
    UserConflictException,
)
from auth_service.api.services import (
    get_db_service,
    get_mail_service,
    get_security_service,
)
from auth_service.db.service import (
    DBService,
    TooManyNewcomersWithSameEmail,
    UserAlreadyExists,
)
from auth_service.mail.service import MailService
from auth_service.models.user import Newcomer, NewcomerRegistered
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
        422: responses.unprocessable_entity_or_password_invalid,
        409: responses.conflict,
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
