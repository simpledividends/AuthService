from enum import Enum

from pydantic import BaseSettings, HttpUrl, PostgresDsn


class Environment(str, Enum):
    TEST = "TEST"
    PRODUCTION = "PRODUCTION"


class Config(BaseSettings):

    class Config:
        case_sensitive = False


class LogConfig(Config):
    level: str = "INFO"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"

    class Config:
        case_sensitive = False
        fields = {
            "level": {
                "env": ["log_level"]
            },
        }


class SecurityConfig(Config):
    min_password_strength: int = 3
    password_hash_rounds: int = 100_000
    password_salt_size: int = 32
    registration_token_lifetime_seconds: float = 3600 * 24 * 7
    change_email_token_lifetime_seconds: float = 3600 * 24
    password_token_lifetime_seconds: float = 3600 * 24
    access_token_lifetime_seconds: float = 60 * 10
    refresh_token_lifetime_seconds: float = 3600 * 24 * 1


class DBPoolConfig(Config):
    db_url: PostgresDsn
    min_size: int = 0
    max_size: int = 20
    max_queries: int = 1000
    max_inactive_connection_lifetime: int = 3600
    timeout: float = 10
    command_timeout: float = 10
    statement_cache_size: int = 1024
    max_cached_statement_lifetime: int = 3600


class DBConfig(Config):
    max_active_newcomers_with_same_email: int = 3
    max_active_requests_change_same_email: int = 2
    max_active_user_password_tokens = 2

    n_transaction_retries: int = 10
    transaction_retry_interval_first: float = 0.01
    transaction_retry_interval_factor: float = 2

    db_pool_config: DBPoolConfig


class SendgridConfig(Config):
    sendgrid_url: HttpUrl
    sendgrid_api_key: str
    aiohttp_pool_size: int = 100
    aiohttp_session_timeout: float = 5


class MailConfig(Config):
    mail_domain: str
    register_verify_link_template: str
    change_email_link_template: str
    reset_password_link_template: str

    sendgrid_config: SendgridConfig


class ServiceConfig(Config):
    service_name: str = "auth_service"
    request_id_header: str = "X-Request-Id"
    environment: str = Environment.TEST

    log_config: LogConfig
    security_config: SecurityConfig
    db_config: DBConfig
    mail_config: MailConfig


def get_config() -> ServiceConfig:
    return ServiceConfig(
        log_config=LogConfig(),
        security_config=SecurityConfig(),
        db_config=DBConfig(db_pool_config=DBPoolConfig()),
        mail_config=MailConfig(sendgrid_config=SendgridConfig()),
    )
