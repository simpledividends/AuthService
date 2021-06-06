import typing as tp
from http import HTTPStatus

from starlette.testclient import TestClient


def test_ping(
    get_client: tp.Callable[[], TestClient],
) -> None:
    with get_client() as client:
        response = client.get("/ping")
    assert response.status_code == HTTPStatus.OK

    expected_body = {"message": "pong"}
    assert response.json() == expected_body
