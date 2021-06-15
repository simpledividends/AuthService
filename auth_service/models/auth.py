from pydantic.main import BaseModel

from .common import Email


class VerificationRequest(BaseModel):
    token: str


class Credentials(BaseModel):
    email: Email
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
