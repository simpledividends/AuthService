import json
import typing as tp
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from socket import AF_INET

import aiohttp
from aiohttp import BasicAuth
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, HttpUrl

from auth_service.models.common import Email
from auth_service.models.token import TokenStr
from auth_service.models.user import Newcomer, User

from .config import (
    CHANGE_EMAIL_HTML,
    CHANGE_EMAIL_SENDER,
    CHANGE_EMAIL_SUBJECT,
    CHANGE_EMAIL_TEXT_TEMPLATE,
    REGISTRATION_EMAIL_SENDER,
    REGISTRATION_EMAIL_SUBJECT,
    REGISTRATION_EMAIL_TEXT_TEMPLATE,
    REGISTRATION_MAIL_HTML,
    RESET_PASSWORD_HTML,
    RESET_PASSWORD_SENDER,
    RESET_PASSWORD_SUBJECT,
    RESET_PASSWORD_TEXT_TEMPLATE,
)

TEMPLATES_PATH = Path(__file__).parent / "templates"


class SendMailError(Exception):

    def __init__(self, status: int, resp: tp.Union[tp.Dict, str]) -> None:
        super().__init__()
        self.status = status
        self.resp = resp


class MailService(BaseModel):
    mail_domain: str
    register_verify_link_template: str
    change_email_link_template: str
    reset_password_link_template: str

    async def send_mail(
        self,
        from_user: str,
        email: Email,
        subject: str,
        text: str,
        html: str,
    ) -> None:
        raise NotImplementedError()

    async def send_registration_letter(
        self,
        newcomer: Newcomer,
        token: TokenStr,
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
        token: TokenStr,
    ) -> None:
        jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_PATH),
            autoescape=True,
        )
        template = jinja_env.get_template(CHANGE_EMAIL_HTML)
        link = self.change_email_link_template.format(token=token)
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

    async def send_forgot_password_letter(
        self,
        user: User,
        token: TokenStr,
    ) -> None:
        jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_PATH),
            autoescape=True,
        )
        template = jinja_env.get_template(RESET_PASSWORD_HTML)
        link = self.reset_password_link_template.format(token=token)
        context = {
            "user": user,
            "link": link,
        }
        rendered = template.render(context)
        text = RESET_PASSWORD_TEXT_TEMPLATE.format(link=link)
        await self.send_mail(
            from_user=RESET_PASSWORD_SENDER.format(domain=self.mail_domain),
            email=user.email,
            subject=RESET_PASSWORD_SUBJECT,
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

    @contextmanager
    def _open_session(self) -> tp.Iterator[aiohttp.ClientSession]:
        session = self._get_session()
        try:
            yield session
        finally:
            session.close()

    async def send_mail(
        self,
        from_user: str,
        email: Email,
        subject: str,
        text: str,
        html: str,
    ) -> None:
        with self._open_session() as session:
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
                resp_text = await resp.text()
                print("resp_text: ", resp_text)
                print("self.mailgun_url: ", self.mailgun_url)
                print("data: ", {
                    "from": from_user,
                    "to": email,
                    "subject": subject,
                    "text": text,
                    "html": html,
                })
                if resp.status != HTTPStatus.OK:
                    raise SendMailError(resp.status, resp_text)
                try:
                    resp_json = json.loads(resp_text)
                except json.JSONDecodeError:
                    raise SendMailError(resp.status, resp_text)
                if "id" not in resp_json:
                    raise SendMailError(resp.status, resp_json)
