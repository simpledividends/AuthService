import secrets
import string
import typing as tp
from datetime import timedelta
from uuid import UUID

from passlib import hash as phash
from pydantic.main import BaseModel
from zxcvbn import zxcvbn

from .models.common import Email
from .models.token import (
    AccessToken,
    ChangeEmailToken,
    PasswordToken,
    RefreshToken,
    RegistrationToken,
    Token,
    TokenStr,
)
from .utils import utc_now

ALPHABET = string.ascii_letters + string.digits
TOKEN_LENGTH = 64


class SecurityService(BaseModel):
    min_password_strength: int
    password_hash_rounds: int
    password_salt_size: int
    registration_token_lifetime: timedelta
    change_email_token_lifetime: timedelta
    password_token_lifetime: timedelta
    access_token_lifetime: timedelta
    refresh_token_lifetime: timedelta

    @staticmethod
    def calc_password_strength(password: str) -> int:
        report = zxcvbn(password)
        score = report["score"]
        return score

    def is_password_proper(self, password: str) -> bool:
        strength = self.calc_password_strength(password)
        return strength >= self.min_password_strength

    def hash_password(self, password: str) -> str:
        return (
            phash.pbkdf2_sha256
            .using(
                salt_size=self.password_salt_size,
                rounds=self.password_hash_rounds,
            )
            .hash(password)
        )

    @staticmethod
    def is_password_correct(
        checked_password: str,
        hashed_password: str,
    ) -> bool:
        return phash.pbkdf2_sha256.verify(checked_password, hashed_password)

    @staticmethod
    def hash_token_string(token_string: TokenStr) -> str:
        return phash.hex_sha256.hash(token_string)

    @staticmethod
    def generate_token_string() -> TokenStr:
        return "".join(secrets.choice(ALPHABET) for _ in range(TOKEN_LENGTH))

    def make_token(self, lifetime: timedelta) -> tp.Tuple[TokenStr, Token]:
        now = utc_now()
        token_string = self.generate_token_string()
        token = Token(
            token=self.hash_token_string(token_string),
            created_at=now,
            expired_at=now + lifetime,
        )
        return token_string, token

    def make_registration_token(
        self,
        user_id: UUID,
    ) -> tp.Tuple[TokenStr, RegistrationToken]:
        token_string, token = self.make_token(self.registration_token_lifetime)
        registration_token = RegistrationToken(**token.dict(), user_id=user_id)
        return token_string, registration_token

    def make_change_email_token(
        self,
        user_id: UUID,
        email: Email,
    ) -> tp.Tuple[TokenStr, ChangeEmailToken]:
        token_string, token = self.make_token(self.change_email_token_lifetime)
        change_email_token = ChangeEmailToken(
            **token.dict(),
            user_id=user_id,
            email=email,
        )
        return token_string, change_email_token

    def make_password_token(
        self,
        user_id: UUID,
    ) -> tp.Tuple[TokenStr, PasswordToken]:
        token_string, token = self.make_token(self.password_token_lifetime)
        password_token = PasswordToken(**token.dict(), user_id=user_id)
        return token_string, password_token

    def make_access_token(
        self,
        session_id: UUID,
    ) -> tp.Tuple[TokenStr, AccessToken]:
        token_string, token = self.make_token(self.access_token_lifetime)
        access_token = AccessToken(**token.dict(), session_id=session_id)
        return token_string, access_token

    def make_refresh_token(
        self,
        session_id: UUID,
    ) -> tp.Tuple[TokenStr, RefreshToken]:
        token_string, token = self.make_token(self.refresh_token_lifetime)
        refresh_token = RefreshToken(**token.dict(), session_id=session_id)
        return token_string, refresh_token
