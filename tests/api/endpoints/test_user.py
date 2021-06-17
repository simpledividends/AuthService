import typing as tp
from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import orm
from starlette.testclient import TestClient

from auth_service.db.models import UserTable
from auth_service.models.user import User, UserRole
from auth_service.security import SecurityService
from tests.helpers import DBObjectCreator, create_authorized_user, make_db_user

ME_PATH = "/auth/users/me"
MY_PASSWORD = "/auth/users/me/password"
USER_PATH_TEMPLATE = "/auth/users/{user_id}"


def test_get_me_success(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> None:
    user_id, access_token = create_authorized_user(
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
    assert resp_json["user_id"] == user_id


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
    user_id, access_token = create_authorized_user(
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
    assert resp_json["user_id"] == user_id
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
