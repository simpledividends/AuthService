import typing as tp
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

T = tp.TypeVar("T", bound="Token")


class Token(BaseModel):
    token: str
    created_at: datetime
    expired_at: datetime


class RegistrationToken(Token):
    user_id: UUID
