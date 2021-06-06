import asyncio
from concurrent.futures.thread import ThreadPoolExecutor
import typing as tp

import uvloop
from fastapi import FastAPI


from .endpoints import add_routes
from .events import add_events
from .exception_handlers import add_exception_handlers
from .middlewares import add_middlewares
from ..log import app_logger, setup_logging
from ..settings import ServiceConfig

__all__ = ("create_app",)


def setup_asyncio() -> None:
    uvloop.install()

    loop = asyncio.get_event_loop()

    executor = ThreadPoolExecutor(thread_name_prefix="auth_service")
    loop.set_default_executor(executor)

    def handler(_, context: tp.Dict[str, tp.Any]) -> None:
        message = "Caught asyncio exception: {message}".format_map(context)
        app_logger.warning(message)

    loop.set_exception_handler(handler)


def create_app(config: ServiceConfig) -> FastAPI:
    setup_logging()
    setup_asyncio()

    app = FastAPI()

    add_events(app)
    add_routes(app)
    add_middlewares(app, config.request_id_header)
    add_exception_handlers(app)

    return app
