from http import HTTPStatus

from starlette.testclient import TestClient

from auth_service.settings import ServiceConfig


def test_ping(
    client: TestClient,
) -> None:
    with client:
        response = client.get("/ping")
    assert response.status_code == HTTPStatus.OK

    expected_body = {"message": "pong"}
    assert response.json() == expected_body


def test_request_id_in_response(
    client: TestClient,
    service_config: ServiceConfig,
) -> None:
    request_id = "some_request_id"
    with client:
        response = client.get(
            "/ping",
            headers={service_config.request_id_header: request_id}
        )
    assert response.status_code == HTTPStatus.OK
    assert response.headers[service_config.request_id_header] == request_id


def test_health(
    client: TestClient,
) -> None:
    with client:
        response = client.get("/health")
    assert response.status_code == HTTPStatus.OK
