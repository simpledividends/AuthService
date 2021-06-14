import typing as tp
from http import HTTPStatus

import pytest
from sqlalchemy import orm
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
    user_id, token_pair = create_authorized_user(
        security_service,
        create_db_object,
    )

    with client:
        resp = client.post(
            GET_ME_PATH,
            headers={"Authorization": f"Bearer {token_pair.access_token}"}
        )

    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert set(resp_json.keys()) == set(User.schema()['properties'].keys())
    assert resp_json["user_id"] == user_id


@pytest.mark.parametrize(
    "header_name,header_value_beginning,token,expected_error_key",
    (
        ("NotAuthorization", "Bearer ", None, "authorization.not_set"),
        ("Authorization", "Bearer", None, "authorization.scheme_unrecognised"),
        ("Authorization", "NotBearer ", None, "authorization.scheme_invalid"),
        ("Authorization", "Bearer ", "incorrect_token", "forbidden"),
    )
)
def test_get_me_forbidden(
    client: TestClient,
    db_session: orm.Session,
    create_db_object: DBObjectCreator,
    security_service: SecurityService,
    header_name: str,
    header_value_beginning: str,
    token: tp.Optional[str],
    expected_error_key: str,
) -> None:
    _, token_pair = create_authorized_user(
        security_service,
        create_db_object,
    )
    token = token or token_pair.access_token

    with client:
        resp = client.post(
            GET_ME_PATH,
            headers={header_name: header_value_beginning + token}
        )

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()["errors"][0]["error_key"] == expected_error_key
