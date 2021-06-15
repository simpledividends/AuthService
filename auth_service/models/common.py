import typing as tp

from pydantic import BaseModel
from pydantic.networks import EmailStr


class Error(BaseModel):
    error_key: str
    error_message: str
    error_loc: tp.Optional[tp.Any] = None


class ErrorResponse(BaseModel):
    errors: tp.List[Error]


class Email(EmailStr):

    @classmethod
    def validate(cls, value: str) -> str:
        return super().validate(value).strip().lower()
