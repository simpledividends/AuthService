from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, EmailStr, constr


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


Name = constr(strip_whitespace=True, min_length=1, max_length=50)


class Email(EmailStr):

    @classmethod
    def validate(cls, value: str) -> str:
        return super().validate(value).strip().lower()


class NewcomerBase(BaseModel):
    name: Name  # type: ignore
    email: Email


class NewcomerRegistered(NewcomerBase):
    password: str


class Newcomer(NewcomerBase):
    user_id: UUID
    created_at: datetime


class User(Newcomer):
    verified_at: datetime
    role: UserRole
