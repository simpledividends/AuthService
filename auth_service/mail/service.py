import typing as tp
from http import HTTPStatus
from pathlib import Path
from socket import AF_INET

import aiohttp
from aiohttp import BasicAuth
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, HttpUrl

from auth_service.models.user import Newcomer, User

from .config import (
    REGISTRATION_EMAIL_SENDER,
    REGISTRATION_EMAIL_SUBJECT,
    REGISTRATION_EMAIL_TEXT_TEMPLATE,
    REGISTRATION_MAIL_HTML,
    CHANGE_EMAIL_HTML,
    CHANGE_EMAIL_SENDER,
    CHANGE_EMAIL_SUBJECT,
    CHANGE_EMAIL_TEXT_TEMPLATE,
)
from ..models.common import Email

TEMPLATES_PATH = Path(__file__).parent / "templates"


class SendMailError(Exception):

    def __init__(self, status: int, resp: tp.Dict[tp.Any, tp.Any]) -> None:
        super().__init__()
        self.status = status
        self.resp = resp


class MailService(BaseModel):
    mail_domain: str
    register_verify_link_template: str
    change_email_link_template: str

    async def send_mail(
        self,
        from_user,
        email: str,
        subject: str,
        text: str,
        html: str,
    ) -> None:
        raise NotImplementedError()

    async def send_registration_letter(
        self,
        newcomer: Newcomer,
        token: str,
    ) -> None:
        jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_PATH),
            autoescape=True,
        )
        template = jinja_env.get_template(REGISTRATION_MAIL_HTML)
        link = self.register_verify_link_template.format(token=token)
        context = {
            "newcomer": newcomer,
            "link": link,
        }
        rendered = template.render(context)
        text = REGISTRATION_EMAIL_TEXT_TEMPLATE.format(link=link)
        await self.send_mail(
            from_user=REGISTRATION_EMAIL_SENDER.format(
                domain=self.mail_domain,
            ),
            email=newcomer.email,
            subject=REGISTRATION_EMAIL_SUBJECT,
            text=text,
            html=rendered,
        )

    async def send_change_email_letter(
        self,
        user: User,
        new_email: Email,
        token: str,
    ) -> None:
        jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_PATH),
            autoescape=True,
        )
        template = jinja_env.get_template(CHANGE_EMAIL_HTML)
        link = self.register_verify_link_template.format(token=token)
        context = {
            "user": user,
            "link": link,
        }
        rendered = template.render(context)
        text = CHANGE_EMAIL_TEXT_TEMPLATE.format(link=link)
        await self.send_mail(
            from_user=CHANGE_EMAIL_SENDER.format(domain=self.mail_domain),
            email=new_email,
            subject=CHANGE_EMAIL_SUBJECT,
            text=text,
            html=rendered,
        )


class MailgunMailService(MailService):
    mailgun_url: HttpUrl
    mailgun_api_key: str
    aiohttp_pool_size: int
    aiohttp_session_timeout: float

    def _get_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.aiohttp_session_timeout),
            connector=aiohttp.TCPConnector(
                family=AF_INET,
                limit_per_host=self.aiohttp_pool_size,
            )
        )

    async def send_mail(
        self,
        from_user,
        email: Email,
        subject: str,
        text: str,
        html: str,
    ) -> None:
        session = self._get_session()
        async with session.post(
            url=self.mailgun_url,
            auth=BasicAuth("api", self.mailgun_api_key),
            data={
                "from": from_user,
                "to": email,
                "subject": subject,
                "text": text,
                "html": html,
            }
        ) as resp:
            if resp.status != HTTPStatus.OK:
                raise SendMailError(resp.status, await resp.json())
