from pydantic import BaseSettings


class LogConfig(BaseSettings):
    level: str = "INFO"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"

    class Config:
        case_sensitive = False
        fields = {
            "level": {
                "env": ["log_level"]
            },
        }


class ServiceConfig(BaseSettings):
    service_name: str = "auth_service"
    request_id_header: str = "X-Request-Id"

    log_config: LogConfig

    class Config:
        case_sensitive = False


def get_config() -> ServiceConfig:
    return ServiceConfig(
        log_config=LogConfig(),
    )
