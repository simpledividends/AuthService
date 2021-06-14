from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class VerificationRequest(BaseModel):
    token: str


class Token(BaseModel):
    token: str
    created_at: datetime
    expired_at: datetime


class RegistrationToken(Token):
    user_id: UUID
