from fastapi import FastAPI

from .health import router as health_router
from .registration import router as registration_router
from .session import router as session_router
from .user import router as user_router


def add_routes(app: FastAPI) -> None:
    for router in (
        health_router,
        registration_router,
        session_router,
        user_router,
    ):
        app.include_router(router)
