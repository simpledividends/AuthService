import asyncio
import typing as tp

import pytest
from sqlalchemy import orm

from auth_service.db.exceptions import (
    TooManyNewcomersWithSameEmail,
    UserAlreadyExists,
)
from auth_service.db.models import Base, NewcomerTable, UserTable
from auth_service.db.service import DBService
from auth_service.models.user import NewcomerRegistered
from auth_service.settings import ServiceConfig
from tests.helpers import make_db_newcomer, make_db_registration_token


@pytest.mark.asyncio
async def test_registration_when_newcomers_exist_with_parallel_requests(
    service_config: ServiceConfig,
    db_service: DBService,
    db_session: orm.Session,
) -> None:
    newcomer = NewcomerRegistered(name="ada", email="a@b.c", password="pass")
    max_same_newcomers = service_config.max_newcomers_with_same_email
    tasks = [
        db_service.create_newcomer(newcomer)
        for _ in range(max_same_newcomers * 3)
    ]

    await db_service.setup()
    try:
        await asyncio.gather(*tasks)
    except TooManyNewcomersWithSameEmail:
        pass
    finally:
        await db_service.cleanup()

    assert len(db_session.query(NewcomerTable).all()) == max_same_newcomers


@pytest.mark.asyncio
async def test_verification_when_users_exist_with_parallel_requests(
    service_config: ServiceConfig,
    db_service: DBService,
    db_session: orm.Session,
    create_db_object: tp.Callable[[Base], None]
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
