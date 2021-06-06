from fastapi import FastAPI

from auth_service.log import app_logger


def add_events(app: FastAPI) -> None:
    async def startup_event() -> None:
        app_logger.info("startup")

    async def shutdown_event() -> None:
        app_logger.info("shutdown")

    app.add_event_handler("startup", startup_event)
    app.add_event_handler("shutdown", shutdown_event)
