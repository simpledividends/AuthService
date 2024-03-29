# pylint: disable=redefined-outer-name

import os
import typing as tp
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path

import pytest
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from alembic import command as alembic_command
from alembic import config as alembic_config
from fastapi import FastAPI
from pytest_httpserver import HTTPServer
from sqlalchemy import orm
from starlette.testclient import TestClient

from auth_service.api.app import create_app
from auth_service.api.services import make_db_service, make_security_service
from auth_service.db.models import Base
from auth_service.db.service import DBService
from auth_service.security import SecurityService
from auth_service.settings import ServiceConfig, get_config

from .constants import (
    CHANGE_EMAIL_LINK_TEMPLATE,
    MAIL_DOMAIN,
    REGISTER_VERIFY_LINK_TEMPLATE,
    RESET_PASSWORD_LINK_TEMPLATE,
    SENDGRID_API_KEY,
)
from .helpers import (
    DBObjectCreator,
    FakeSendgridServer,
    check_access_forbidden,
)

CURRENT_DIR = Path(__file__).parent
ALEMBIC_INI_PATH = CURRENT_DIR.parent / "alembic.ini"


@contextmanager
def sqlalchemy_bind_context(url: str) -> tp.Iterator[sa.engine.Engine]:
    bind = sa.engine.create_engine(url)
    try:
        yield bind
    finally:
        bind.dispose()


@contextmanager
def sqlalchemy_session_context(
    bind: sa.engine.Engine,
) -> tp.Iterator[orm.Session]:
    session_factory = orm.sessionmaker(bind)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def migrations_context(alembic_ini: Path) -> tp.Iterator[None]:
    cfg = alembic_config.Config(alembic_ini)

    alembic_command.upgrade(cfg, "head")
    try:
        yield
    finally:
        alembic_command.downgrade(cfg, "base")


@pytest.fixture(scope="session")
def db_url() -> str:
    return os.getenv("DB_URL")


@pytest.fixture(scope="session")
def db_bind(db_url: str) -> tp.Iterator[sa.engine.Engine]:
    with sqlalchemy_bind_context(db_url) as bind:
        yield bind


@pytest.fixture
def db_session(db_bind: sa.engine.Engine) -> tp.Iterator[orm.Session]:
    with migrations_context(ALEMBIC_INI_PATH):
        with sqlalchemy_session_context(db_bind) as session:
            yield session


@pytest.fixture
def fake_sendgrid_server() -> FakeSendgridServer:
    return FakeSendgridServer()


@pytest.fixture
def sendgrid_server_url(
    httpserver: HTTPServer,
    fake_sendgrid_server: FakeSendgridServer,
) -> str:
    path = "/send_mail"
    send_mail_url = f"http://127.0.0.1:{httpserver.port}{path}"
    (
        httpserver
        .expect_request(path, "POST")
        .respond_with_handler(
            func=fake_sendgrid_server.handle_send_mail_request,
        )
    )
    return send_mail_url


@pytest.fixture
def create_db_object(
    db_session: orm.Session,
) -> DBObjectCreator:
    assert db_session.is_active

    def create(obj: Base) -> None:
        db_session.add(obj)
        db_session.commit()

    return create


@pytest.fixture
def set_env(sendgrid_server_url: str) -> tp.Generator[None, None, None]:
    monkeypatch = MonkeyPatch()
    monkeypatch.setenv("MAIL_DOMAIN", MAIL_DOMAIN)
    monkeypatch.setenv(
        "REGISTER_VERIFY_LINK_TEMPLATE",
        REGISTER_VERIFY_LINK_TEMPLATE,
    )
    monkeypatch.setenv(
        "CHANGE_EMAIL_LINK_TEMPLATE",
        CHANGE_EMAIL_LINK_TEMPLATE,
    )
    monkeypatch.setenv(
        "RESET_PASSWORD_LINK_TEMPLATE",
        RESET_PASSWORD_LINK_TEMPLATE,
    )
    monkeypatch.setenv("SENDGRID_API_KEY", SENDGRID_API_KEY)
    monkeypatch.setenv("SENDGRID_URL", sendgrid_server_url)

    yield

    monkeypatch.undo()


@pytest.fixture
def service_config(set_env: None) -> ServiceConfig:
    return get_config()


@pytest.fixture
def security_service(service_config: ServiceConfig) -> SecurityService:
    return make_security_service(service_config)


@pytest.mark.asyncio
@pytest.fixture
async def db_service(service_config: ServiceConfig) -> DBService:
    return make_db_service(service_config)


@pytest.fixture
def app(service_config: ServiceConfig, db_session: orm.Session) -> FastAPI:
    app = create_app(service_config)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app=app)


@pytest.fixture
def access_forbidden_check(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> tp.Callable[[tp.Dict[str, tp.Any]], None]:

    def check(request_params: tp.Dict[str, tp.Any]) -> None:
        check_access_forbidden(
            client,
            security_service,
            create_db_object,
            request_params,
        )

    return check


@pytest.fixture
def access_not_found_check(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> tp.Callable[[tp.Dict[str, tp.Any]], None]:

    def check(request_params: tp.Dict[str, tp.Any]) -> None:
        check_access_forbidden(
            client,
            security_service,
            create_db_object,
            request_params,
            expected_status=HTTPStatus.NOT_FOUND,
        )

    return check
