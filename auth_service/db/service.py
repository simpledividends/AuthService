import asyncio
import typing as tp
from functools import partial
from uuid import uuid4

from asyncpg import Connection, SerializationError
from asyncpg.pool import Pool
from pydantic import BaseModel

from auth_service.db.exceptions import (
    TokenNotFound,
    TooManyNewcomersWithSameEmail,
    UserAlreadyExists,
)
from auth_service.log import app_logger
from auth_service.models.token import RegistrationToken
from auth_service.models.user import Newcomer, NewcomerRegistered
from auth_service.utils import utc_now

T = tp.TypeVar("T")


class DBService(BaseModel):
    pool: Pool
    max_newcomers_with_same_email: int
    n_transaction_retries: int
    transaction_retry_interval_first: float
    transaction_retry_interval_factor: float

    class Config:
        arbitrary_types_allowed = True

    async def setup(self) -> None:
        await self.pool
        app_logger.info("Auth service initialized")

    async def cleanup(self) -> None:
        await self.pool.close()
        app_logger.info("Auth service shutdown")

    async def ping(self) -> bool:
        return await self.pool.fetchval("SELECT TRUE;")

    async def execute_serializable_transaction(
        self,
        func: tp.Callable[[Connection], tp.Awaitable[T]],
    ) -> T:
        interval = self.transaction_retry_interval_first
        async with self.pool.acquire() as conn:
            for attempt in range(self.n_transaction_retries):
                try:
                    async with conn.transaction(isolation="serializable"):
                        result = await func(conn)
                except SerializationError:
                    if attempt == self.n_transaction_retries - 1:
                        raise
                    await asyncio.sleep(interval)
                    interval *= self.transaction_retry_interval_factor
                else:
                    break
        return result

    async def create_newcomer(self, newcomer: NewcomerRegistered) -> Newcomer:
        func = partial(self._create_newcomer, newcomer=newcomer)
        created = await self.execute_serializable_transaction(func)
        return created

    async def _create_newcomer(
        self,
        conn: Connection,
        newcomer: NewcomerRegistered,
    ) -> Newcomer:
        email = newcomer.email

        n_users = await self._count_users_by_email(conn, email)
        if n_users > 0:
            raise UserAlreadyExists()

        n_newcomers = await self._count_newcomers_by_email(conn, email)
        if n_newcomers >= self.max_newcomers_with_same_email:
            raise TooManyNewcomersWithSameEmail()

        created = await self._insert_newcomer(conn, newcomer)
        return created

    @staticmethod
    async def _count_users_by_email(conn: Connection, email: str) -> int:
        query = """
            SELECT count(*)
            FROM users
            WHERE email = $1::VARCHAR;
        """
        n_users = await conn.fetchval(query, email)
        return n_users

    @staticmethod
    async def _count_newcomers_by_email(conn: Connection, email: str) -> int:
        query = """
                SELECT count(*)
                FROM newcomers
                WHERE email = $1::VARCHAR;
            """
        n_newcomers = await conn.fetchval(query, email)
        return n_newcomers

    @staticmethod
    async def _insert_newcomer(
        conn: Connection,
        newcomer: NewcomerRegistered,
    ) -> Newcomer:
        query = """
            INSERT INTO newcomers
                (user_id, name, email, password, created_at)
            VALUES
                (
                    $1::UUID
                    , $2::VARCHAR
                    , $3::VARCHAR
                    , $4::VARCHAR
                    , $5::TIMESTAMP
                )
            RETURNING
                user_id
                , name
                , email
                , created_at
            ;
        """
        record = await conn.fetchrow(
            query,
            uuid4(),
            newcomer.name,
            newcomer.email,
            newcomer.password,
            utc_now(),
        )
        return Newcomer(**record)

    async def save_registration_token(self, token: RegistrationToken) -> None:
        query = """
            INSERT INTO registration_tokens
                (token, user_id, created_at, expired_at)
            VALUES
                (
                    $1::VARCHAR
                    , $2::UUID
                    , $3::TIMESTAMP
                    , $4::TIMESTAMP
                )
            ;
        """
        await self.pool.execute(
            query,
            token.token,
            token.user_id,
            token.created_at,
            token.expired_at,
        )
