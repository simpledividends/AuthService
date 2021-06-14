import typing as tp
from http import HTTPStatus

from starlette.testclient import TestClient

from auth_service.models.user import User
from auth_service.security import SecurityService
from tests.helpers import DBObjectCreator, create_authorized_user

GET_ME_PATH = "/auth/users/me"


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
        resp = client.post(
            GET_ME_PATH,
            headers={"Authorization": f"Bearer {access_token}"}
        )

    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert set(resp_json.keys()) == set(User.schema()['properties'].keys())
    assert resp_json["user_id"] == user_id


def test_get_me_forbidden(
    access_forbidden_check: tp.Callable[[str], None]
) -> None:
    access_forbidden_check(GET_ME_PATH)
