import typing as tp

from pydantic import BaseModel  # pylint: disable=no-name-in-module


class Error(BaseModel):
    error_key: str
    error_message: str
    error_loc: tp.Optional[tp.Any] = None
