import typing as tp
from http import HTTPStatus
from uuid import uuid4

from starlette.testclient import TestClient

from auth_service.models.user import UserRole, User
from auth_service.security import SecurityService
from tests.helpers import DBObjectCreator, create_authorized_user, make_db_user


USER_PATH_TEMPLATE = "/auth/users/{user_id}"


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
