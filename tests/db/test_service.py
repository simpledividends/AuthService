import asyncio
import typing as tp
from uuid import uuid4

import pytest
from sqlalchemy import orm

from auth_service.db.exceptions import (
    PasswordInvalid,
    TooManyChangeSameEmailRequests,
    TooManyNewcomersWithSameEmail,
    TooManyPasswordTokens,
    UserAlreadyExists,
)
from auth_service.db.models import (
    EmailTokenTable,
    NewcomerTable,
    PasswordTokenTable,
    UserTable,
)
from auth_service.db.service import DBService
from auth_service.models.common import Email
from auth_service.models.user import NewcomerFull
from auth_service.security import SecurityService
from auth_service.settings import ServiceConfig
from auth_service.utils import utc_now
from tests.helpers import (
    DBObjectCreator,
    make_db_newcomer,
    make_db_registration_token,
    make_db_user,
    make_email_token,
)

pytestmark = pytest.mark.asyncio

ExcT = tp.TypeVar("ExcT", bound=Exception)


async def is_func_executed(
    func: tp.Awaitable[tp.Any],
    exc_cls: tp.Type[ExcT],
) -> bool:
    try:
        await func
    except exc_cls:
        return False
    return True


async def test_registration_when_newcomers_exist_with_parallel_requests(
    service_config: ServiceConfig,
    db_service: DBService,
    db_session: orm.Session,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    email = Email("a@b.c")
    max_same_newcomers = (
        service_config
        .db_config
        .max_active_newcomers_with_same_email
    )
    newcomers = [
        NewcomerFull(
            name="ada",
            email=email,
            hashed_password="pass",
            user_id=uuid4(),
            created_at=utc_now()
        )
        for _ in range(max_same_newcomers * 3)
    ]
    registration_tokens = [
        security_service.make_registration_token(newcomer.user_id)[1]
        for newcomer in newcomers
    ]

    tasks = [
        db_service.create_newcomer(newcomer, token)
        for newcomer, token in zip(newcomers, registration_tokens)
    ]

    await db_service.setup()
    try:
        await asyncio.gather(*tasks)
    except TooManyNewcomersWithSameEmail:
        pass
    finally:
        await db_service.cleanup()

    assert len(db_session.query(NewcomerTable).all()) == max_same_newcomers


async def test_verification_when_users_exist_with_parallel_requests(
    service_config: ServiceConfig,
    db_service: DBService,
    db_session: orm.Session,
    create_db_object: DBObjectCreator
) -> None:
    n = 10

    token_hashes = [f"token_{i}_hash" for i in range(n)]
    for hashed in token_hashes:
        newcomer = make_db_newcomer(email="e@m.ail")
        token = make_db_registration_token(hashed, user_id=newcomer.user_id)
        create_db_object(newcomer)
        create_db_object(token)

    tasks = [
        db_service.verify_newcomer(token_hash)
        for token_hash in token_hashes
    ]

    await db_service.setup()
    try:
        await asyncio.gather(*tasks)
    except UserAlreadyExists:
        pass
    finally:
        await db_service.cleanup()

    assert len(db_session.query(UserTable).all()) == 1


async def test_update_passwords_with_parallel_requests(
    service_config: ServiceConfig,
    db_service: DBService,
    db_session: orm.Session,
    create_db_object: DBObjectCreator
) -> None:
    n = 10
    user = make_db_user()
    create_db_object(user)

    new_passwords = [f"hashed_password_{i}" for i in range(n)]

    def is_password_valid(password: str) -> bool:
        return password == user.password

    tasks = [
        is_func_executed(
            db_service.update_password_if_old_is_valid(
                user_id=user.user_id,
                new_password=new_password,
                is_old_password_valid=is_password_valid,
            ),
            PasswordInvalid,
        )
        for new_password in new_passwords
    ]

    await db_service.setup()
    try:
        execution_statuses = await asyncio.gather(*tasks)
    finally:
        await db_service.cleanup()

    assert sum(execution_statuses) == 1


async def test_many_change_same_email_parallel_requests(
    service_config: ServiceConfig,
    db_service: DBService,
    db_session: orm.Session,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    email = Email("a@b.c")

    max_email_changes = (
        service_config
        .db_config
        .max_active_requests_change_same_email
    )
    users = [make_db_user() for _ in range(max_email_changes * 3)]
    for user in users:
        create_db_object(user)
    change_email_tokens = [
        security_service.make_change_email_token(user.user_id, email)[1]
        for user in users
    ]
    tasks = [
        db_service.add_change_email_token(token)
        for token in change_email_tokens
    ]

    await db_service.setup()
    try:
        await asyncio.gather(*tasks)
    except TooManyChangeSameEmailRequests:
        pass
    finally:
        await db_service.cleanup()

    assert len(db_session.query(EmailTokenTable).all()) == max_email_changes


async def test_verify_same_email_with_parallel_requests(
    service_config: ServiceConfig,
    db_service: DBService,
    db_session: orm.Session,
    create_db_object: DBObjectCreator
) -> None:
    n = 10

    email = "new@email.ru"
    token_hashes = [f"token_{i}_hash" for i in range(n)]
    for hashed in token_hashes:
        user = make_db_user()
        token = make_email_token(hashed, user_id=user.user_id, email=email)
        create_db_object(user)
        create_db_object(token)

    tasks = [
        is_func_executed(
            db_service.verify_email(token_hash),
            UserAlreadyExists,
        )
        for token_hash in token_hashes
    ]

    await db_service.setup()
    try:
        results = await asyncio.gather(*tasks)
    finally:
        await db_service.cleanup()

    assert sum(results) == 1


async def test_many_forgot_password_parallel_requests(
    service_config: ServiceConfig,
    db_service: DBService,
    db_session: orm.Session,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    max_password_tokens = (
        service_config
        .db_config
        .max_active_user_password_tokens
    )

    user = make_db_user()
    create_db_object(user)

    password_tokens = [
        security_service.make_password_token(user.user_id)[1]
        for _ in range(max_password_tokens * 3)
    ]
    tasks = [
        db_service.create_password_token(token)
        for token in password_tokens
    ]

    await db_service.setup()
    try:
        await asyncio.gather(*tasks)
    except TooManyPasswordTokens:
        pass
    finally:
        await db_service.cleanup()

    assert (
        len(db_session.query(PasswordTokenTable).all())
        == max_password_tokens
    )
