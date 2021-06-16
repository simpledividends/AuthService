from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, constr

from auth_service.models.common import Email


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


Name = constr(strip_whitespace=True, min_length=1, max_length=50)


class NewcomerInfo(BaseModel):
    name: Name  # type: ignore


class NewcomerBase(NewcomerInfo):
    email: Email


class NewcomerRegistered(NewcomerBase):
    password: str


class Newcomer(NewcomerBase):
    user_id: UUID
    created_at: datetime


class UserInfo(NewcomerInfo):
    pass


class User(Newcomer):
    verified_at: datetime
    role: UserRole


class PasswordPair(BaseModel):
    password: str
    new_password: str
