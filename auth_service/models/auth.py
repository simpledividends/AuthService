from pydantic.main import BaseModel

from .common import Email
from .token import TokenStr


class TokenBody(BaseModel):
    token: TokenStr


class TokenPasswordBody(TokenBody):
    password: str


class EmailBody(BaseModel):
    email: Email


class Credentials(BaseModel):
    email: Email
    password: str


class TokenPair(BaseModel):
    access_token: TokenStr
    refresh_token: TokenStr
