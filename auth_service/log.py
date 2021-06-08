import logging.config

from .context import REQUEST_ID
from .settings import get_config


app_logger = logging.getLogger("app")
access_logger = logging.getLogger("access")


ACCESS_LOG_FORMAT = (
    'remote_addr="%a" '
    'referer="%{Referer}i" '
    'user_agent="%{User-Agent}i" '
    'protocol="%r" '
    'response_code="%s" '
    'request_time="%Tf" '
)

config = get_config()
LEVEL = config.log_config.level
DATETIME_FORMAT = config.log_config.datetime_format


class ServiceNameFilter(logging.Filter):

    def __init__(self, name: str = ""):
        self.service_name = config.service_name

        super().__init__(name)

    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "service_name", self.service_name)

        return super().filter(record)


class RequestIDFilter(logging.Filter):
    def __init__(self, name: str = ""):
        self.context_var = REQUEST_ID

        super().__init__(name)

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = self.context_var.get("-")
        setattr(record, "request_id", request_id)
        return super().filter(record)


CONFIG = {
        "version": 1,
        "disable_existing_loggers": True,
        "loggers": {
            "root": {
                "level": LEVEL,
                "handlers": ["console"],
                "propagate": False,
            },
            app_logger.name: {
                "level": LEVEL,
                "handlers": ["console"],
                "propagate": False,
            },
            access_logger.name: {
                "level": LEVEL,
                "handlers": ["access"],
                "propagate": False,
            },
            "gunicorn.error": {
                "level": "INFO",
                "handlers": [
                    "console",
                ],
                "propagate": False,
            },
            "gunicorn.access": {
                "level": "ERROR",
                "handlers": [
                    "gunicorn.access",
                ],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": [
                    "console",
                ],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "ERROR",
                "handlers": [
                    "gunicorn.access",
                ],
                "propagate": False,
            },
        },
        "handlers": {
            "console": {
                "formatter": "console",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": ["service_name", "request_id"],
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": ["service_name", "request_id"],
            },
            "gunicorn.access": {
                "class": "logging.StreamHandler",
                "formatter": "gunicorn.access",
                "stream": "ext://sys.stdout",
                "filters": ["service_name", "request_id"],
            },
        },
        "formatters": {
            "console": {
                "format": (
                    'time="%(asctime)s" '
                    'level="%(levelname)s" '
                    'service_name="%(service_name)s" '
                    'logger="%(name)s" '
                    'pid="%(process)d" '
                    'request_id="%(request_id)s" '
                    'message="%(message)s" '
                ),
                "datefmt": DATETIME_FORMAT,
            },
            "access": {
                "format": (
                    'time="%(asctime)s" '
                    'level="%(levelname)s" '
                    'service_name="%(service_name)s" '
                    'logger="%(name)s" '
                    'pid="%(process)d" '
                    'request_id="%(request_id)s" '
                    'method="%(method)s" '
                    'requested_url="%(requested_url)s" '
                    'status_code="%(status_code)s" '
                    'request_time="%(request_time)s" '
                ),
                "datefmt": DATETIME_FORMAT,
            },
            "gunicorn.access": {
                "format": (
                    'time="%(asctime)s" '
                    'level="%(levelname)s" '
                    'logger="%(name)s" '
                    'pid="%(process)d" '
                    'request_id="%(request_id)s" '
                    '"%(message)s"'
                ),
                "datefmt": DATETIME_FORMAT,
            },
        },
        "filters": {
            "service_name": {"()": "auth_service.log.ServiceNameFilter"},
            "request_id": {"()": "auth_service.log.RequestIDFilter"},
        },
    }


def setup_logging() -> None:
    logging.config.dictConfig(CONFIG)
