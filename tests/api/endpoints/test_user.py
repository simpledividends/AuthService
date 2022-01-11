import re
import typing as tp
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from sqlalchemy import orm
from starlette.testclient import TestClient

from auth_service.db.models import (
    AccessTokenTable,
    EmailTokenTable,
    PasswordTokenTable,
    SessionTable,
    UserTable,
)
from auth_service.mail.config import (
    CHANGE_EMAIL_SENDER,
    CHANGE_EMAIL_SUBJECT,
    RESET_PASSWORD_SENDER,
    RESET_PASSWORD_SUBJECT,
)
from auth_service.models.user import User
from auth_service.security import SecurityService
from auth_service.settings import ServiceConfig
from auth_service.utils import utc_now
from tests.constants import (
    CHANGE_EMAIL_LINK_TEMPLATE,
    RESET_PASSWORD_LINK_TEMPLATE,
)
from tests.helpers import (
    DBObjectCreator,
    FakeSendgridServer,
    assert_all_tables_are_empty,
    create_authorized_user,
    make_db_newcomer,
    make_db_registration_token,
    make_db_user,
    make_email_token,
    make_password_token,
)
from tests.utils import ApproxDatetime

ME_PATH = "/users/me"
MY_PASSWORD = "/users/me/password"
MY_EMAIL = "/users/me/email"
VERIFY_EMAIL_PATH = "/users/me/email/verify"
FORGOT_PASSWORD_PATH = "/users/me/password/forgot"
RESET_PASSWORD_PATH = "/users/me/password/reset"


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

    new_info = {
        "name": "my_new_name",
        "marketing_agree": False,
    }
    with client:
        resp = client.patch(
            ME_PATH,
            headers={"Authorization": f"Bearer {access_token}"},
            json=new_info,
        )

    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert set(resp_json.keys()) == set(User.schema()['properties'].keys())
    assert resp_json["user_id"] == user.user_id
    assert resp_json["name"] == new_info["name"]
    assert resp_json["marketing_agree"] == new_info["marketing_agree"]

    users = db_session.query(UserTable).all()
    assert len(users) == 1
    assert users[0].name == new_info["name"]
    assert users[0].marketing_agree == new_info["marketing_agree"]


@pytest.mark.parametrize(
    "request_body,expected_error_key",
    (
        (None, "value_error.missing"),
        ({"email": "a@b.c"}, "value_error.missing"),
        ({"name": {"a": "b"}}, "type_error.str"),
        ({"name": ""}, "value_error.any_str.min_length"),
        ({"name": "a" * 129}, "value_error.any_str.max_length"),
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


def test_patch_email_success(
    client: TestClient,
    create_db_object: DBObjectCreator,
    security_service: SecurityService,
    db_session: orm.Session,
    service_config: ServiceConfig,
    fake_sendgrid_server: FakeSendgridServer,
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
    assert len(fake_sendgrid_server.requests) == 1
    send_mail_request = fake_sendgrid_server.requests[0]
    assert send_mail_request.headers["Authorization"] == \
        f"Bearer {service_config.mail_config.sendgrid_config.sendgrid_api_key}"
    assert (
        send_mail_request.json["from"] == {
            "email": CHANGE_EMAIL_SENDER.username
            + f"@{service_config.mail_config.mail_domain}",
            "name": CHANGE_EMAIL_SENDER.name,
        }
    )
    assert (
        send_mail_request.json["personalizations"]
        == [{"to": [{"email": new_email}]}]
    )
    assert send_mail_request.json["subject"] == CHANGE_EMAIL_SUBJECT

    contents = send_mail_request.json["content"]
    assert contents[0]["type"] == "text/plain"
    assert contents[1]["type"] == "text/html"
    link_pattern = (
        CHANGE_EMAIL_LINK_TEMPLATE
        .replace("{token}", r"(\w+)")
        .replace("?", r"\?")
    )
    text_token = re.findall(link_pattern, contents[0]["value"])[0]
    html_token = re.findall(link_pattern, contents[1]["value"])[0]
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


@pytest.mark.parametrize(
    "new_email",
    ("new e.mail", "", "a@b.c" + "c" * 124)
)
def test_patch_my_email_with_invalid_email(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
    new_email: str,
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
            json={"password": "pass", "new_email": new_email},
        )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json()["errors"][0]["error_key"] == "value_error.email"


def test_patch_my_email_when_user_exists(
    client: TestClient,
    create_db_object: DBObjectCreator,
    security_service: SecurityService,
    db_session: orm.Session,
    fake_sendgrid_server: FakeSendgridServer,
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
    assert len(fake_sendgrid_server.requests) == 0


def test_patch_my_email_when_newcomers_exist(
    client: TestClient,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    db_session: orm.Session,
    security_service: SecurityService,
    fake_sendgrid_server: FakeSendgridServer,
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
    assert len(fake_sendgrid_server.requests) == 0


def test_patch_my_email_when_requests_for_email_change_exist(
    client: TestClient,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    db_session: orm.Session,
    security_service: SecurityService,

    fake_sendgrid_server: FakeSendgridServer,
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
    assert len(fake_sendgrid_server.requests) == 0


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


def test_email_verify_user_already_exists(
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


def test_forgot_password_success(
    client: TestClient,
    create_db_object: DBObjectCreator,
    security_service: SecurityService,
    db_session: orm.Session,
    service_config: ServiceConfig,
    fake_sendgrid_server: FakeSendgridServer,
):
    user = make_db_user()
    create_db_object(user)

    now = utc_now()
    with client:
        resp = client.post(
            FORGOT_PASSWORD_PATH,
            json={"email": " " + user.email.capitalize() + "   "},
        )

    # Check response
    assert resp.status_code == HTTPStatus.ACCEPTED
    assert resp.json() == {}

    # # Check DB content
    assert_all_tables_are_empty(db_session, [UserTable, PasswordTokenTable])
    assert len(db_session.query(UserTable).all()) == 1
    password_tokens = db_session.query(PasswordTokenTable).all()
    assert len(password_tokens) == 1
    password_token = password_tokens[0]

    assert password_token.user_id == user.user_id
    assert password_token.created_at == ApproxDatetime(now)
    assert password_token.expired_at == ApproxDatetime(
        now
        + timedelta(
            seconds=service_config
            .security_config
            .password_token_lifetime_seconds,
        )
    )

    # Check sent mail
    assert len(fake_sendgrid_server.requests) == 1
    send_mail_request = fake_sendgrid_server.requests[0]
    assert send_mail_request.headers["Authorization"] == \
        f"Bearer {service_config.mail_config.sendgrid_config.sendgrid_api_key}"
    assert (
        send_mail_request.json["from"] == {
            "email": RESET_PASSWORD_SENDER.username
            + f"@{service_config.mail_config.mail_domain}",
            "name": RESET_PASSWORD_SENDER.name,
        }
    )
    assert (
        send_mail_request.json["personalizations"]
        == [{"to": [{"email": user.email}]}]
    )
    assert send_mail_request.json["subject"] == RESET_PASSWORD_SUBJECT

    contents = send_mail_request.json["content"]
    assert contents[0]["type"] == "text/plain"
    assert contents[1]["type"] == "text/html"
    link_pattern = (
        RESET_PASSWORD_LINK_TEMPLATE
        .replace("{token}", r"(\w+)")
        .replace("?", r"\?")
    )
    text_token = re.findall(link_pattern, contents[0]["value"])[0]
    html_token = re.findall(link_pattern, contents[1]["value"])[0]
    assert text_token == html_token
    assert (
        security_service.hash_token_string(text_token)
        == password_token.token
    )


def test_forgot_password_with_invalid_email(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:

    with client:
        resp = client.post(
            FORGOT_PASSWORD_PATH,
            json={"email": "not_a_email"},
        )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json()["errors"][0]["error_key"] == "value_error.email"


def test_forgot_password_when_email_not_exists(
    client: TestClient,
    db_session: orm.Session,
    fake_sendgrid_server: FakeSendgridServer,
):
    with client:
        resp = client.post(
            FORGOT_PASSWORD_PATH,
            json={"email": "a@b.c"},
        )

    assert resp.status_code == HTTPStatus.ACCEPTED
    assert resp.json() == {}

    assert_all_tables_are_empty(db_session)
    assert len(fake_sendgrid_server.requests) == 0


def test_forgot_password_when_too_many_requests(
    client: TestClient,
    service_config: ServiceConfig,
    create_db_object: DBObjectCreator,
    security_service: SecurityService,
    db_session: orm.Session,
    fake_sendgrid_server: FakeSendgridServer,
):
    max_password_tokens = (
        service_config
        .db_config
        .max_active_user_password_tokens
    )

    user = make_db_user()
    create_db_object(user)

    # Add expired token to check that it does not affect
    expired_token = make_password_token(
        user_id=user.user_id,
        expired_at=utc_now() - timedelta(1),
    )
    create_db_object(expired_token)

    for i in range(max_password_tokens + 1):
        with client:
            resp = client.post(
                FORGOT_PASSWORD_PATH,
                json={"email": user.email},
            )
        assert resp.status_code == HTTPStatus.ACCEPTED

        n_tokens = len(db_session.query(PasswordTokenTable).all())
        n_mails = len(fake_sendgrid_server.requests)
        if i < max_password_tokens:
            assert n_tokens == i + 2
            assert n_mails == i + 1
        else:
            assert n_tokens == i + 1
            assert n_mails == i


def test_password_reset_success(
    client: TestClient,
    db_session: orm.Session,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    user = make_db_user()
    token_string = "abracadabra"
    token_hashed = security_service.hash_token_string(token_string)
    token = make_password_token(token_hashed, user_id=user.user_id)
    create_db_object(user)
    create_db_object(token)

    password = "VeryH@rdPa$$w0rd"
    with client:
        resp = client.post(
            RESET_PASSWORD_PATH,
            json={"token": token_string, "password": password},
        )
    assert resp.status_code == HTTPStatus.OK

    assert_all_tables_are_empty(db_session, [UserTable])
    users = db_session.query(UserTable).all()
    assert len(users) == 1
    assert security_service.is_password_correct(password, users[0].password)


def test_reset_password_with_weak_new_password(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    with client:
        resp = client.post(
            RESET_PASSWORD_PATH,
            json={"token": "hashed_token", "password": "weak"},
        )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        resp.json()["errors"][0]["error_key"]
        == "value_error.password.improper"
    )


@pytest.mark.parametrize(
    "token_string,expired_at",
    (
        ("other_token", utc_now() + timedelta(days=10)),
        ("my_token", utc_now() - timedelta(days=10)),
    )
)
def test_reset_password_incorrect_token(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
    db_session: orm.Session,
    token_string: str,
    expired_at: datetime,
) -> None:
    old_password = "old_pass"
    user = make_db_user(password=security_service.hash_password(old_password))
    token_hashed = security_service.hash_token_string(token_string)
    token = make_password_token(
        token_hashed,
        user_id=user.user_id,
        expired_at=expired_at,
    )
    create_db_object(user)
    create_db_object(token)

    password = "VeryH@rdPa$$w0rd"
    with client:
        resp = client.post(
            RESET_PASSWORD_PATH,
            json={"token": "my_token", "password": password},
        )
    assert resp.status_code == HTTPStatus.FORBIDDEN

    assert len(db_session.query(PasswordTokenTable).all()) == 1
    users = db_session.query(UserTable).all()
    assert len(users) == 1
    user = users[0]
    assert security_service.is_password_correct(old_password, user.password)
