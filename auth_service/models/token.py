from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from .common import Email


class Token(BaseModel):
    token: str
    created_at: datetime
    expired_at: datetime


class UserToken(Token):
    user_id: UUID


class SessionToken(Token):
    session_id: UUID


class RegistrationToken(UserToken):
    pass


class ChangeEmailToken(UserToken):
    email: Email


class AccessToken(SessionToken):
    pass


class RefreshToken(SessionToken):
    pass
