from datetime import timedelta

from asyncpg.pool import create_pool
from fastapi import FastAPI

from auth_service.db.service import DBService
from auth_service.mail.service import MailService, MailgunMailService
from auth_service.security import SecurityService
from auth_service.settings import ServiceConfig


def get_db_service(app: FastAPI) -> DBService:
    return app.state.db_service


def get_mail_service(app: FastAPI) -> MailService:
    return app.state.mail_service


def get_security_service(app: FastAPI) -> SecurityService:
    return app.state.security_service


def make_db_service(config: ServiceConfig) -> DBService:
    db_config = config.db_config.dict()
    pool_config = db_config.pop("db_pool_config")
    pool_config["dsn"] = pool_config.pop("db_url")
    pool = create_pool(**pool_config)
    service = DBService(pool=pool, **db_config)
    return service


def make_security_service(config: ServiceConfig) -> SecurityService:
    security_config = config.security_config.dict()
    for token_type in (
        "registration",
        "change_email",
        "password", 
        "access",
        "refresh",
    ):
        security_config[f"{token_type}_token_lifetime"] = timedelta(
            seconds=security_config.pop(f"{token_type}_token_lifetime_seconds")
        )
    service = SecurityService(**security_config)
    return service


def make_mail_service(config: ServiceConfig) -> MailgunMailService:
    mail_config = config.mail_config.dict()
    mailgun_config = mail_config.pop("mailgun_config")
    service = MailgunMailService(**{**mail_config, **mailgun_config})
    return service
