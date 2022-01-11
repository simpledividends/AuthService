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
        prepared = super().validate(value).strip().lower()
        if len(prepared) > 128:
            raise ValueError("Email length must be less or equal to 128")
        return prepared
