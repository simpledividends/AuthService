from http import HTTPStatus

from starlette.testclient import TestClient


def test_ping(
    client: TestClient,
) -> None:
    with client:
        response = client.get("/ping")
    assert response.status_code == HTTPStatus.OK

    expected_body = {"message": "pong"}
    assert response.json() == expected_body


def test_health(
    client: TestClient,
) -> None:
    with client:
        response = client.get("/health")
    assert response.status_code == HTTPStatus.OK
