from pydantic.main import BaseModel

from .common import Email


class TokenBody(BaseModel):
    token: str


class TokenPasswordBody(TokenBody):
    password: str


class EmailBody(BaseModel):
    email: Email


class Credentials(BaseModel):
    email: Email
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
