# pylint: disable=redefined-outer-name)


import typing as tp

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from auth_service.api.app import create_app
from auth_service.settings import get_config


@pytest.fixture
def app() -> FastAPI:
    config = get_config()
    app = create_app(config)
    return app


@pytest.fixture
def get_client(app: FastAPI) -> tp.Callable[[], TestClient]:

    def client() -> TestClient:
        return TestClient(app=app)
    return client
