import typing as tp
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from socket import AF_INET

import aiohttp
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, HttpUrl

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
        from_email: str,
        from_name: str,
        to_email: str,
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
        sender = REGISTRATION_EMAIL_SENDER
        await self.send_mail(
            from_email=f"{sender.username}@{self.mail_domain}",
            from_name=sender.name,
            to_email=newcomer.email,
            subject=REGISTRATION_EMAIL_SUBJECT,
            text=text,
            html=rendered,
        )

    async def send_change_email_letter(
        self,
        user: User,
        new_email: str,
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
        sender = CHANGE_EMAIL_SENDER
        await self.send_mail(
            from_email=f"{sender.username}@{self.mail_domain}",
            from_name=sender.name,
            to_email=new_email,
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
        sender = RESET_PASSWORD_SENDER
        await self.send_mail(
            from_email=f"{sender.username}@{self.mail_domain}",
            from_name=sender.name,
            to_email=user.email,
            subject=RESET_PASSWORD_SUBJECT,
            text=text,
            html=rendered,
        )


class SendgridMailService(MailService):
    sendgrid_url: HttpUrl
    sendgrid_api_key: str
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

    @asynccontextmanager
    async def _open_session(self) -> tp.AsyncIterator[aiohttp.ClientSession]:
        session = self._get_session()
        try:
            yield session
        finally:
            await session.close()

    async def send_mail(
        self,
        from_email: str,
        from_name: str,
        to_email: str,
        subject: str,
        text: str,
        html: str,
    ) -> None:
        async with self._open_session() as session:
            async with session.post(
                url=self.sendgrid_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.sendgrid_api_key}",
                },
                json={
                    "personalizations": [{"to": [{"email": to_email}]}],
                    "from": {"email": from_email, "name": from_name},
                    "subject": subject,
                    "content": [
                        {
                            "type": "text/plain",
                            "value": text,
                        },
                        {
                            "type": "text/html",
                            "value": html,
                        },
                    ],
                }
            ) as resp:
                if resp.status != HTTPStatus.ACCEPTED:
                    resp_text = await resp.text()
                    raise SendMailError(resp.status, resp_text)
