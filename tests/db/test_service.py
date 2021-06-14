import asyncio

import pytest
from sqlalchemy import orm

from auth_service.db.models import NewcomerTable
from auth_service.db.service import DBService, TooManyNewcomersWithSameEmail
from auth_service.models.user import NewcomerRegistered
from auth_service.settings import ServiceConfig


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
