from pydantic import BaseSettings, HttpUrl, PostgresDsn


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
    n_transaction_retries: int = 10
    transaction_retry_interval_first: float = 0.01
    transaction_retry_interval_factor: float = 2

    db_pool_config: DBPoolConfig


class MailgunConfig(Config):
    mailgun_url: HttpUrl
    mailgun_api_key: str
    aiohttp_pool_size: int = 100
    aiohttp_session_timeout: float = 5


class MailConfig(Config):
    mail_domain: str
    register_verify_link_template: str

    mailgun_config: MailgunConfig


class ServiceConfig(Config):
    service_name: str = "auth_service"
    request_id_header: str = "X-Request-Id"
    max_newcomers_with_same_email: int = 3

    log_config: LogConfig
    security_config: SecurityConfig
    db_config: DBConfig
    mail_config: MailConfig


def get_config() -> ServiceConfig:
    return ServiceConfig(
        log_config=LogConfig(),
        security_config=SecurityConfig(),
        db_config=DBConfig(db_pool_config=DBPoolConfig()),
        mail_config=MailConfig(mailgun_config=MailgunConfig()),
    )
