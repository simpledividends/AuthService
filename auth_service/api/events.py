from fastapi import FastAPI

from auth_service.log import app_logger
from auth_service.settings import ServiceConfig

from .services import get_db_service, make_db_service


def add_events(app: FastAPI, config: ServiceConfig) -> None:
    async def startup_event() -> None:
        app_logger.info("Startup started")
        # Do initialization here because of asyncio/asyncpg error
        # https://github.com/sqlalchemy/sqlalchemy/issues/6409
        app.state.db_service = make_db_service(config)
        await get_db_service(app).setup()
        app_logger.info("Startup finished")

    async def shutdown_event() -> None:
        app_logger.info("Shutdown started")
        await get_db_service(app).cleanup()
        app_logger.info("Shutdown finished")

    app.add_event_handler("startup", startup_event)
    app.add_event_handler("shutdown", shutdown_event)
