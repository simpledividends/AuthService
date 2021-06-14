import secrets
import string
import typing as tp
from datetime import timedelta
from uuid import UUID

from passlib import hash as phash
from pydantic.main import BaseModel
from zxcvbn import zxcvbn

from auth_service.models.token import RegistrationToken
from auth_service.utils import utc_now

ALPHABET = string.ascii_letters + string.digits
TOKEN_LENGTH = 64


class SecurityService(BaseModel):
    min_password_strength: int
    password_hash_rounds: int
    password_salt_size: int
    registration_token_lifetime: timedelta

    @staticmethod
    def calc_password_strength(password: str) -> int:
        report = zxcvbn(password)
        score = report["score"]
        return score

    def is_password_valid(self, password: str) -> bool:
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
    def hash_token_string(token_string: str) -> str:
        return phash.hex_sha256.hash(token_string)

    @staticmethod
    def generate_token_string() -> str:
        return "".join(secrets.choice(ALPHABET) for _ in range(TOKEN_LENGTH))

    def make_registration_token(
        self,
        user_id: UUID,
    ) -> tp.Tuple[str, RegistrationToken]:
        now = utc_now()
        token_string = self.generate_token_string()
        token = RegistrationToken(
            user_id=user_id,
            token=self.hash_token_string(token_string),
            created_at=now,
            expired_at=now + self.registration_token_lifetime,
        )
        return token_string, token
