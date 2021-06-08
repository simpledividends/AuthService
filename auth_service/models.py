import typing as tp
from enum import Enum

from pydantic import BaseModel  # pylint: disable=no-name-in-module


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class UserStatus(str, Enum):
    active = "active"
    deleted = "deleted"


class Error(BaseModel):
    error_key: str
    error_message: str
    error_loc: tp.Optional[tp.Any] = None
