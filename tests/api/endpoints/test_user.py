import re
import typing as tp
from datetime import datetime, timedelta
from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import orm
from starlette.testclient import TestClient

from auth_service.db.models import (
    AccessTokenTable,
    EmailTokenTable,
    SessionTable,
    UserTable,
)
from auth_service.mail.config import CHANGE_EMAIL_SENDER, CHANGE_EMAIL_SUBJECT
from auth_service.models.user import User, UserRole
from auth_service.security import SecurityService
from auth_service.settings import ServiceConfig
from auth_service.utils import utc_now
from tests.constants import CHANGE_EMAIL_LINK_TEMPLATE
from tests.helpers import (
    DBObjectCreator,
    FakeMailgunServer,
    assert_all_tables_are_empty,
    create_authorized_user,
    make_db_newcomer,
    make_db_registration_token,
    make_db_user,
    make_email_token,
)
from tests.utils import ApproxDatetime

ME_PATH = "/auth/users/me"
MY_PASSWORD = "/auth/users/me/password"
MY_EMAIL = "/auth/users/me/email"
VERIFY_EMAIL_PATH = "/auth/email/verify"
USER_PATH_TEMPLATE = "/auth/users/{user_id}"


def test_get_me_success(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    user, access_token = create_authorized_user(
        security_service,
        create_db_object,
    )

    with client:
        resp = client.get(
            ME_PATH,
            headers={"Authorization": f"Bearer {access_token}"}
        )

    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert set(resp_json.keys()) == set(User.schema()['properties'].keys())
    assert resp_json["user_id"] == user.user_id


def test_get_me_forbidden(
    access_forbidden_check: tp.Callable[[tp.Dict[str, tp.Any]], None]
) -> None:
    access_forbidden_check({"method": "GET", "url": ME_PATH})


def test_patch_me_success(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
    db_session: orm.Session,
) -> None:
    user, access_token = create_authorized_user(
        security_service,
        create_db_object,
    )

    new_name = "my_new_name"
    with client:
        resp = client.patch(
            ME_PATH,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"name": new_name},
        )

    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert set(resp_json.keys()) == set(User.schema()['properties'].keys())
    assert resp_json["user_id"] == user.user_id
    assert resp_json["name"] == new_name

    users = db_session.query(UserTable).all()
    assert len(users) == 1
    assert users[0].name == new_name


@pytest.mark.parametrize(
    "request_body,expected_error_key",
    (
        (None, "value_error.missing"),
        ({"email": "a@b.c"}, "value_error.missing"),
        ({"name": {"a": "b"}}, "type_error.str"),
        ({"name": ""}, "value_error.any_str.min_length"),
        ({"name": "a" * 51}, "value_error.any_str.max_length"),
    )
)
def test_patch_me_validation_errors(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
    request_body: tp.Optional[tp.Dict[str, tp.Any]],
    expected_error_key: str,
):
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
    )
    with client:
        resp = client.patch(
            ME_PATH,
            headers={"Authorization": f"Bearer {access_token}"},
            json=request_body,
        )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    resp_json = resp.json()
    assert resp_json["errors"][0]["error_key"] == expected_error_key


def test_patch_me_forbidden(
    access_forbidden_check: tp.Callable[[tp.Dict[str, tp.Any]], None]
) -> None:
    access_forbidden_check({"method": "PATCH", "url": ME_PATH})


def test_patch_my_password_success(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
    db_session: orm.Session
) -> None:
    password = "old_password"
    new_password = "Very$tr0ng!"
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
        hashed_password=security_service.hash_password(password),
    )
    with client:
        resp = client.patch(
            MY_PASSWORD,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": password, "new_password": new_password},
        )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {}

    users = db_session.query(UserTable).all()
    assert len(users) == 1
    assert security_service.is_password_correct(
        new_password,
        users[0].password,
    )


def test_patch_my_password_forbidden(
    access_forbidden_check: tp.Callable[[tp.Dict[str, tp.Any]], None]
) -> None:
    access_forbidden_check({"method": "PATCH", "url": MY_PASSWORD})


def test_patch_my_password_with_invalid_old_password(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
        hashed_password=security_service.hash_password("pass"),
    )
    with client:
        resp = client.patch(
            MY_PASSWORD,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": "invalid", "new_password": "Very$tr0ng!"},
        )

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()["errors"][0]["error_key"] == "password.invalid"


def test_patch_my_password_with_weak_new_password(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
    )
    with client:
        resp = client.patch(
            MY_PASSWORD,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": "pass", "new_password": "weak"},
        )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        resp.json()["errors"][0]["error_key"]
        == "value_error.password.improper"
    )


def test_change_email_success(
    client: TestClient,
    create_db_object: DBObjectCreator,
    security_service: SecurityService,
    db_session: orm.Session,
    service_config: ServiceConfig,
    fake_mailgun_server: FakeMailgunServer,
):
    password = "Str0ngPa$$"
    hashed_password = security_service.hash_password(password)
    user, access_token = create_authorized_user(
        security_service,
        create_db_object,
        hashed_password=hashed_password,
    )

    new_email = "new@e.mail"
    request_email = "  NeW@e.maiL "
    now = utc_now()
    with client:
        resp = client.patch(
            MY_EMAIL,
            json={"password": password, "new_email": request_email},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    # Check response
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {}

    # # Check DB content
    assert_all_tables_are_empty(
        db_session,
        [UserTable, EmailTokenTable, SessionTable, AccessTokenTable]
    )
    users = db_session.query(UserTable).all()
    assert len(users) == 1
    assert users[0].email == user.email
    email_tokens = db_session.query(EmailTokenTable).all()
    assert len(email_tokens) == 1
    email_token = email_tokens[0]

    assert email_token.user_id == user.user_id
    assert email_token.email == new_email
    assert email_token.created_at == ApproxDatetime(now)
    assert email_token.expired_at == ApproxDatetime(
        now
        + timedelta(
            seconds=service_config
            .security_config
            .change_email_token_lifetime_seconds,
        )
    )

    # Check sent mail
    assert len(fake_mailgun_server.requests) == 1
    send_mail_request = fake_mailgun_server.requests[0]
    assert send_mail_request.authorization == {
        "username": "api",
        "password": service_config.mail_config.mailgun_config.mailgun_api_key,
    }
    assert (
        send_mail_request.form["from"]
        == CHANGE_EMAIL_SENDER.format(
            domain=service_config.mail_config.mail_domain
        )
    )
    assert send_mail_request.form["to"] == new_email
    assert send_mail_request.form["subject"] == CHANGE_EMAIL_SUBJECT

    link_pattern = (
        CHANGE_EMAIL_LINK_TEMPLATE
        .replace("{token}", r"(\w+)")
        .replace("?", r"\?")
    )
    text_token = re.findall(link_pattern, send_mail_request.form["text"])[0]
    html_token = re.findall(link_pattern, send_mail_request.form["html"])[0]
    assert text_token == html_token
    assert security_service.hash_token_string(text_token) == email_token.token


def test_patch_my_email_forbidden(
    access_forbidden_check: tp.Callable[[tp.Dict[str, tp.Any]], None]
) -> None:
    access_forbidden_check({"method": "PATCH", "url": MY_EMAIL})


def test_patch_my_email_with_invalid_password(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
        hashed_password=security_service.hash_password("pass"),
    )
    with client:
        resp = client.patch(
            MY_EMAIL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": "invalid", "new_email": "new@e.mail"},
        )

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()["errors"][0]["error_key"] == "password.invalid"


def test_patch_my_email_with_invalid_email(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
        hashed_password=security_service.hash_password("pass"),
    )
    with client:
        resp = client.patch(
            MY_EMAIL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": "pass", "new_email": "new e.mail"},
        )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json()["errors"][0]["error_key"] == "value_error.email"


def test_patch_my_email_when_user_exists(
    client: TestClient,
    create_db_object: DBObjectCreator,
    security_service: SecurityService,
    db_session: orm.Session,
    fake_mailgun_server: FakeMailgunServer,
) -> None:
    new_email = "new@e.mail"
    create_db_object(make_db_user(email=new_email))

    password = "pass"
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
        hashed_password=security_service.hash_password(password),
    )

    with client:
        resp = client.patch(
            MY_EMAIL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": password, "new_email": new_email},
        )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()["errors"][0]["error_key"] == "email.already_exists"

    assert len(db_session.query(EmailTokenTable).all()) == 0
    assert len(fake_mailgun_server.requests) == 0


def test_patch_my_email_when_newcomers_exist(
    client: TestClient,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    db_session: orm.Session,
    security_service: SecurityService,
    fake_mailgun_server: FakeMailgunServer,
) -> None:
    max_same_newcomers = (
        service_config
        .db_config
        .max_active_newcomers_with_same_email
    )

    new_email = "new@e.mail"
    for i in range(max_same_newcomers):
        newcomer = make_db_newcomer(email=new_email)
        create_db_object(newcomer)
        reg_token = make_db_registration_token(
            token=f"hashed_token_{i}",
            user_id=newcomer.user_id,
        )
        create_db_object(reg_token)

    password = "pass"
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
        hashed_password=security_service.hash_password(password),
    )

    with client:
        resp = client.patch(
            MY_EMAIL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": password, "new_email": new_email},
        )

    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()["errors"][0]["error_key"] == "conflict"

    assert len(db_session.query(EmailTokenTable).all()) == 0
    assert len(fake_mailgun_server.requests) == 0


def test_patch_my_email_when_requests_for_email_change_exist(
    client: TestClient,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    db_session: orm.Session,
    security_service: SecurityService,

    fake_mailgun_server: FakeMailgunServer,
) -> None:
    max_email_requests = (
        service_config
        .db_config
        .max_active_requests_change_same_email
    )

    new_email = "new@e.mail"
    for i in range(max_email_requests):
        user = make_db_user()
        create_db_object(user)
        token = make_email_token(
            token=f"hashed_token_{i}",
            user_id=user.user_id,
            email=new_email,
        )
        create_db_object(token)

    password = "pass"
    user, access_token = create_authorized_user(
        security_service,
        create_db_object,
        hashed_password=security_service.hash_password(password),
    )

    with client:
        resp = client.patch(
            MY_EMAIL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": password, "new_email": new_email},
        )

    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()["errors"][0]["error_key"] == "conflict"

    assert len(db_session.query(EmailTokenTable).all()) == max_email_requests
    assert len(fake_mailgun_server.requests) == 0


def test_change_email_verify_success(
    client: TestClient,
    db_session: orm.Session,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    email = "new@e.mail"
    user = make_db_user()
    token_string = "abracadabra"
    token_hashed = security_service.hash_token_string(token_string)
    token = make_email_token(token_hashed, user_id=user.user_id, email=email)
    create_db_object(user)
    create_db_object(token)

    with client:
        resp = client.post(
            VERIFY_EMAIL_PATH,
            json={"token": token_string},
        )
    assert resp.status_code == HTTPStatus.OK

    assert_all_tables_are_empty(db_session, [UserTable])
    users = db_session.query(UserTable).all()
    assert len(users) == 1
    assert users[0].email == email


@pytest.mark.parametrize(
    "token_string,expired_at",
    (
        ("other_token", utc_now() + timedelta(days=10)),
        ("my_token", utc_now() - timedelta(days=10)),
    )
)
def test_register_verify_incorrect_token(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
    token_string: str,
    expired_at: datetime,
) -> None:
    user = make_db_user()
    token_hashed = security_service.hash_token_string(token_string)
    token = make_email_token(
        token_hashed,
        user_id=user.user_id,
        expired_at=expired_at,
    )
    create_db_object(user)
    create_db_object(token)

    with client:
        resp = client.post(
            VERIFY_EMAIL_PATH,
            json={"token": "my_token"},
        )
    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_register_verify_user_already_exists(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    email = "new@e.mail"
    user = make_db_user()
    token_string = "abracadabra"
    token_hashed = security_service.hash_token_string(token_string)
    token = make_email_token(token_hashed, user_id=user.user_id, email=email)
    create_db_object(user)
    create_db_object(token)

    other_user = make_db_user(email=email)
    create_db_object(other_user)

    with client:
        resp = client.post(
            VERIFY_EMAIL_PATH,
            json={"token": token_string},
        )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()["errors"][0]["error_key"] == "email.already_exists"


def test_get_user_success(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
        user_role=UserRole.admin,
    )

    other_user = make_db_user()
    create_db_object(other_user)

    with client:
        resp = client.get(
            USER_PATH_TEMPLATE.format(user_id=other_user.user_id),
            headers={"Authorization": f"Bearer {access_token}"}
        )

    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert set(resp_json.keys()) == set(User.schema()['properties'].keys())
    assert resp_json["user_id"] == other_user.user_id
    assert resp_json["email"] == other_user.email
    assert resp_json["role"] == other_user.role


def test_get_user_forbidden(
    access_forbidden_check: tp.Callable[[tp.Dict[str, tp.Any]], None]
) -> None:
    access_forbidden_check(
        {"method": "GET", "url": USER_PATH_TEMPLATE.format(user_id="uid")}
    )


def test_get_user_not_found_when_not_admin(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
    )

    other_user = make_db_user()
    create_db_object(other_user)

    with client:
        resp = client.get(
            USER_PATH_TEMPLATE.format(user_id=other_user.user_id),
            headers={"Authorization": f"Bearer {access_token}"}
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_get_user_not_found_when_not_exists(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
    )

    with client:
        resp = client.get(
            USER_PATH_TEMPLATE.format(user_id=uuid4()),
            headers={"Authorization": f"Bearer {access_token}"}
        )
    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_get_user_422_when_not_uuid(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    _, access_token = create_authorized_user(
        security_service,
        create_db_object,
    )

    with client:
        resp = client.get(
            USER_PATH_TEMPLATE.format(user_id="uid"),
            headers={"Authorization": f"Bearer {access_token}"}
        )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
