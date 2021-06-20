from datetime import timedelta
from http import HTTPStatus

import pytest
from sqlalchemy import orm
from starlette.testclient import TestClient

from auth_service.db.models import (
    AccessTokenTable,
    RefreshTokenTable,
    SessionTable,
    UserTable,
)
from auth_service.security import SecurityService
from auth_service.settings import ServiceConfig
from auth_service.utils import utc_now
from tests.helpers import (
    DBObjectCreator,
    assert_all_tables_are_empty,
    make_db_user,
)
from tests.utils import ApproxDatetime

LOGIN_PATH = "/auth/login"


def test_login_success(
    client: TestClient,
    db_session: orm.Session,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
    service_config: ServiceConfig,
) -> None:
    password = "some_pass"
    hashed_password = security_service.hash_password(password)
    user = make_db_user(password=hashed_password)
    create_db_object(user)

    now = utc_now()
    with client:
        resp = client.post(
            LOGIN_PATH,
            json={"email": user.email, "password": password},
        )

    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert set(resp_json.keys()) == {"access_token", "refresh_token"}

    access = resp_json["access_token"]
    refresh = resp_json["refresh_token"]

    assert_all_tables_are_empty(
        db_session,
        [UserTable, SessionTable, AccessTokenTable, RefreshTokenTable],
    )
    assert len(db_session.query(UserTable).all()) == 1
    sessions = db_session.query(SessionTable).all()
    access_tokens = db_session.query(AccessTokenTable).all()
    refresh_tokens = db_session.query(RefreshTokenTable).all()
    for rows in (sessions, access_tokens, refresh_tokens):
        assert len(rows) == 1

    session = sessions[0]
    assert session.user_id == user.user_id
    assert session.started_at == ApproxDatetime(now)
    assert session.finished_at is None

    sc = service_config.security_config
    access_lifetime = timedelta(seconds=sc.access_token_lifetime_seconds)
    refresh_lifetime = timedelta(seconds=sc.refresh_token_lifetime_seconds)

    for token, token_string, lifetime in (
        (access_tokens[0], access, access_lifetime),
        (refresh_tokens[0], refresh, refresh_lifetime),
    ):
        assert token.session_id == session.session_id
        assert token.created_at == ApproxDatetime(now)
        assert token.expired_at == ApproxDatetime(now + lifetime)
        assert token.token == security_service.hash_token_string(token_string)


@pytest.mark.parametrize(
    "email,password",
    (
        ("other@e.mail", "my_password"),
        ("my@e.mail", "other_password"),
    )
)
def test_login_forbidden(
    client: TestClient,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
    security_service: SecurityService,
    email: str,
    password: str,
) -> None:
    hashed_password = security_service.hash_password("my_password")
    user = make_db_user(email="my@e.mail", password=hashed_password)
    create_db_object(user)

    with client:
        resp = client.post(
            LOGIN_PATH,
            json={"email": email, "password": password},
        )

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert_all_tables_are_empty(db_session, [UserTable])
