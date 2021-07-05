import asyncio
import typing as tp
from functools import partial
from uuid import UUID, uuid4

from asyncpg import Connection, Record, SerializationError
from asyncpg.pool import Pool
from pydantic import BaseModel

from auth_service.db.exceptions import (
    NotExists,
    PasswordInvalid,
    TokenNotFound,
    TooManyChangeSameEmailRequests,
    TooManyNewcomersWithSameEmail,
    TooManyPasswordTokens,
    UserAlreadyExists,
    UserNotExists, TransactionError,
)
from auth_service.log import app_logger
from auth_service.models.token import (
    AccessToken,
    ChangeEmailToken,
    PasswordToken,
    RefreshToken,
    RegistrationToken,
)
from auth_service.models.user import (
    Newcomer,
    NewcomerFull,
    User,
    UserInfo,
    UserRole,
)
from auth_service.utils import utc_now

T = tp.TypeVar("T")


class DBService(BaseModel):
    pool: Pool
    max_active_newcomers_with_same_email: int
    max_active_requests_change_same_email: int
    max_active_user_password_tokens: int
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
                        raise TransactionError
                    await asyncio.sleep(interval)
                    interval *= self.transaction_retry_interval_factor
                else:
                    break
        return result

    async def create_newcomer(
        self,
        newcomer: NewcomerFull,
        token: RegistrationToken,
    ) -> Newcomer:
        func = partial(self._create_newcomer, newcomer=newcomer, token=token)
        created = await self.execute_serializable_transaction(func)
        return created

    async def _create_newcomer(
        self,
        conn: Connection,
        newcomer: NewcomerFull,
        token: RegistrationToken,
    ) -> Newcomer:
        await self._check_email_available(conn, newcomer.email)
        created = await self._insert_newcomer(conn, newcomer)
        await self._add_registration_token(conn, token)
        return created

    async def _check_email_available(
        self,
        conn: Connection,
        email: str,
    ) -> None:
        n_users = await self._count_users_by_email(conn, email)
        if n_users > 0:
            raise UserAlreadyExists()

        n_newcomers = await self._count_active_newcomers_by_email(conn, email)
        if n_newcomers >= self.max_active_newcomers_with_same_email:
            raise TooManyNewcomersWithSameEmail()

        n_email_changes = await self._count_email_changes(conn, email)
        if n_email_changes >= self.max_active_requests_change_same_email:
            raise TooManyChangeSameEmailRequests()

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
    async def _count_active_newcomers_by_email(
        conn: Connection,
        email: str,
    ) -> int:
        query = """
            SELECT count(*)
            FROM newcomers
                JOIN registration_tokens rt on newcomers.user_id = rt.user_id
            WHERE email = $1::VARCHAR AND rt.expired_at > $2::TIMESTAMP;
        """
        n_newcomers = await conn.fetchval(query, email, utc_now())
        return n_newcomers

    @staticmethod
    async def _count_email_changes(conn: Connection, email: str) -> int:
        query = """
            SELECT count(*)
            FROM email_tokens
            WHERE email = $1::VARCHAR AND expired_at > $2::TIMESTAMP;
        """
        n_changes = await conn.fetchval(query, email, utc_now())
        return n_changes

    @staticmethod
    async def _insert_newcomer(
        conn: Connection,
        newcomer: NewcomerFull,
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
            newcomer.user_id,
            newcomer.name,
            newcomer.email,
            newcomer.hashed_password,
            newcomer.created_at,
        )
        return Newcomer(**record)

    @staticmethod
    async def _add_registration_token(
        conn: Connection,
        token: RegistrationToken,
    ) -> None:
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
        await conn.execute(
            query,
            token.token,
            token.user_id,
            token.created_at,
            token.expired_at,
        )

    async def verify_newcomer(self, token: str) -> User:
        func = partial(self._verify_newcomer, token=token)
        user = await self.execute_serializable_transaction(func)
        return user

    async def _verify_newcomer(self, conn: Connection, token: str) -> User:
        newcomer = await self._get_newcomer_by_token(conn, token)
        if newcomer is None:
            raise TokenNotFound()

        n_users = await self._count_users_by_email(conn, newcomer["email"])
        if n_users > 0:
            raise UserAlreadyExists()

        await self._drop_register_token(conn, token)

        query = """
            INSERT INTO users
                (user_id, name, email, password, created_at, verified_at, role)
            VALUES
                (
                    $1::UUID
                    , $2::VARCHAR
                    , $3::VARCHAR
                    , $4::VARCHAR
                    , $5::TIMESTAMP
                    , $6::TIMESTAMP
                    , $7::role_enum
                )
            RETURNING
                user_id
                , name
                , email
                , created_at
                , verified_at
                , role
            ;
        """
        record = await conn.fetchrow(
            query,
            newcomer["user_id"],
            newcomer["name"],
            newcomer["email"],
            newcomer["password"],
            newcomer["created_at"],
            utc_now(),
            UserRole.user,
        )
        return User(**record)

    @staticmethod
    async def _get_newcomer_by_token(
        conn: Connection,
        token: str,
    ) -> tp.Optional[Record]:
        query = """
            SELECT n.*
            FROM newcomers n
                JOIN registration_tokens rt on n.user_id = rt.user_id
            WHERE token = $1::VARCHAR and expired_at > $2::TIMESTAMP
        """
        record = await conn.fetchrow(query, token, utc_now())
        return record

    @staticmethod
    async def _drop_register_token(conn: Connection, token: str) -> None:
        query = """
            DELETE FROM registration_tokens
            WHERE token = $1::VARCHAR
        """
        await conn.execute(query, token)

    async def get_user_with_password(self, email: str) -> tp.Tuple[UUID, str]:
        query = """
            SELECT user_id, password
            FROM users
            WHERE email = $1::VARCHAR
        """
        record = await self.pool.fetchrow(query, email)
        if record is None:
            raise UserNotExists()
        return record["user_id"], record["password"]

    async def create_session(self, user_id: UUID) -> UUID:
        query = """
            INSERT INTO sessions
                (session_id, user_id, started_at, finished_at)
            VALUES
                (
                    $1::UUID
                    , $2::UUID
                    , $3::TIMESTAMP
                    , $4::TIMESTAMP
                )
            RETURNING
                session_id
            ;
        """
        record = await self.pool.fetchrow(
            query,
            uuid4(),
            user_id,
            utc_now(),
            None,
        )
        return record["session_id"]

    async def add_access_token(self, token: AccessToken) -> None:
        query = """
            INSERT INTO access_tokens
                (token, session_id, created_at, expired_at)
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
            token.session_id,
            token.created_at,
            token.expired_at,
        )

    async def add_refresh_token(self, token: RefreshToken) -> None:
        query = """
            INSERT INTO refresh_tokens
                (token, session_id, created_at, expired_at)
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
            token.session_id,
            token.created_at,
            token.expired_at,
        )

    async def get_user_by_access_token(self, token: str) -> User:
        query = """
            SELECT
                u.user_id
                , u.name
                , u.email
                , u.created_at
                , u.verified_at
                , u.role
            FROM users u
                JOIN sessions s on u.user_id = s.user_id
                JOIN access_tokens t on s.session_id = t.session_id
            WHERE t.token = $1::VARCHAR AND t.expired_at > $2::TIMESTAMP
        """
        record = await self.pool.fetchrow(query, token, utc_now())
        if record is None:
            raise UserNotExists()
        return User(**record)

    async def get_user(self, user_id: UUID) -> User:
        query = """
            SELECT user_id, name, email, created_at, verified_at, role
            FROM users
            WHERE user_id = $1::UUID
        """
        record = await self.pool.fetchrow(query, user_id)
        if record is None:
            raise UserNotExists()
        return User(**record)

    async def finish_session(self, token: str) -> None:
        func = partial(self._finish_session, token=token)
        await self.execute_serializable_transaction(func)

    async def _finish_session(self, conn: Connection, token: str) -> None:
        session_id = await self._get_session_id_by_access_token(conn, token)
        await self._drop_access_tokens(conn, session_id)
        await self._drop_refresh_tokens(conn, session_id)

        query = """
            UPDATE sessions
            SET finished_at = $1::TIMESTAMP
            WHERE session_id = $2::UUID
        """
        await conn.execute(query, utc_now(), session_id)

    @staticmethod
    async def _get_session_id_by_access_token(
        conn: Connection,
        token: str,
    ) -> UUID:
        query = """
            SELECT s.session_id
            FROM sessions s
                JOIN access_tokens t on s.session_id = t.session_id
            WHERE t.token = $1::VARCHAR AND t.expired_at > $2::TIMESTAMP
        """
        session_id = await conn.fetchval(query, token, utc_now())
        if session_id is None:
            raise NotExists()
        return session_id

    @staticmethod
    async def _drop_access_tokens(conn: Connection, session_id: UUID) -> None:
        query = """
            DELETE FROM access_tokens
            WHERE session_id = $1::UUID
        """
        await conn.execute(query, session_id)

    @staticmethod
    async def _drop_refresh_tokens(conn: Connection, session_id: UUID) -> None:
        query = """
            DELETE FROM refresh_tokens
            WHERE session_id = $1::UUID
        """
        await conn.execute(query, session_id)

    async def drop_valid_refresh_token(self, token: str) -> UUID:
        query = """
            DELETE FROM refresh_tokens
            WHERE token = $1::VARCHAR and expired_at > $2::TIMESTAMP
            RETURNING session_id
        """
        session_id = await self.pool.fetchval(query, token, utc_now())
        if session_id is None:
            raise NotExists()
        return session_id

    async def update_user(self, user_id: UUID, user_info: UserInfo) -> User:
        query = """
            UPDATE users
            SET name = $1::VARCHAR
            WHERE user_id = $2::UUID
            RETURNING
                user_id
                , name
                , email
                , created_at
                , verified_at
                , role
        """
        record = await self.pool.fetchrow(query, user_info.name, user_id)
        return User(**record)

    async def update_password_if_old_is_valid(
        self,
        user_id: UUID,
        new_password: str,
        is_old_password_valid: tp.Callable[[str], bool],
    ) -> None:
        func = partial(
            self._update_password_if_old_is_valid,
            user_id=user_id,
            new_password=new_password,
            is_old_password_valid=is_old_password_valid,
        )
        await self.execute_serializable_transaction(func)

    @staticmethod
    async def _update_password_if_old_is_valid(
        conn: Connection,
        user_id: UUID,
        new_password: str,
        is_old_password_valid: tp.Callable[[str], bool],
    ) -> None:
        get_query = """
            SELECT password
            FROM users
            WHERE user_id = $1::UUID
        """
        password = await conn.fetchval(get_query, user_id)

        if password is None:
            raise UserNotExists()

        if not is_old_password_valid(password):
            raise PasswordInvalid()

        update_query = """
            UPDATE users
            SET password = $1::VARCHAR
            WHERE user_id = $2::UUID
        """
        await conn.fetchval(update_query, new_password, user_id)

    async def add_change_email_token(self, token: ChangeEmailToken) -> None:
        func = partial(self._add_change_email_token, token=token)
        await self.execute_serializable_transaction(func)

    async def _add_change_email_token(
        self,
        conn: Connection,
        token: ChangeEmailToken,
    ) -> None:
        await self._check_email_available(conn, token.email)

        query = """
            INSERT INTO email_tokens
                (token, user_id, email, created_at, expired_at)
            VALUES
                (
                    $1::VARCHAR
                    , $2::UUID
                    , $3::VARCHAR
                    , $4::TIMESTAMP
                    , $5::TIMESTAMP
                )
            ;
        """
        await conn.execute(
            query,
            token.token,
            token.user_id,
            token.email,
            token.created_at,
            token.expired_at,
        )

    async def verify_email(self, token: str) -> User:
        func = partial(self._verify_email, token=token)
        user = await self.execute_serializable_transaction(func)
        return user

    async def _verify_email(self, conn: Connection, token: str) -> User:
        query = """
            SELECT user_id, email
            FROM email_tokens
            WHERE token = $1::VARCHAR and expired_at > $2::TIMESTAMP
        """
        record = await conn.fetchrow(query, token, utc_now())
        if record is None:
            raise TokenNotFound()

        n_users = await self._count_users_by_email(conn, record["email"])
        if n_users > 0:
            raise UserAlreadyExists()

        await self._drop_email_token(conn, token)

        query = """
            UPDATE users
            SET email = $1::VARCHAR
            WHERE user_id = $2::UUID
            RETURNING
                user_id
                , name
                , email
                , created_at
                , verified_at
                , role

        """
        record = await conn.fetchrow(query, record["email"], record["user_id"])
        return User(**record)

    @staticmethod
    async def _drop_email_token(conn: Connection, token: str) -> None:
        query = """
            DELETE FROM email_tokens
            WHERE token = $1::VARCHAR
        """
        await conn.execute(query, token)

    async def get_user_by_email(self, email: str) -> User:
        query = """
            SELECT
                user_id
                , name
                , email
                , created_at
                , verified_at
                , role
            FROM users
            WHERE email = $1::VARCHAR
        """
        record = await self.pool.fetchrow(query, email)
        if record is None:
            raise UserNotExists()
        return User(**record)

    async def create_password_token(self, token: PasswordToken) -> None:
        func = partial(self._create_password_token, token=token)
        user = await self.execute_serializable_transaction(func)
        return user

    async def _create_password_token(
        self,
        conn: Connection,
        token: PasswordToken,
    ) -> None:
        query = """
            SELECT user_id
            FROM users
            WHERE user_id = $1::UUID
        """
        if await conn.fetchval(query, token.user_id) is None:
            raise UserNotExists()

        n_tokens = await self._count_password_tokens(conn, token.user_id)
        if n_tokens >= self.max_active_user_password_tokens:
            raise TooManyPasswordTokens()

        query = """
            INSERT INTO password_tokens
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
        await conn.execute(
            query,
            token.token,
            token.user_id,
            token.created_at,
            token.expired_at,
        )

    @staticmethod
    async def _count_password_tokens(conn: Connection, user_id: UUID) -> int:
        query = """
            SELECT count(*)
            FROM password_tokens
            WHERE user_id = $1::UUID AND expired_at > $2::TIMESTAMP;
        """
        n_tokens = await conn.fetchval(query, user_id, utc_now())
        return n_tokens

    async def update_password_by_token(
        self,
        token: str,
        password: str,
    ) -> None:
        func = partial(
            self._update_password_by_token,
            token=token,
            password=password,
        )
        user = await self.execute_serializable_transaction(func)
        return user

    async def _update_password_by_token(
        self,
        conn: Connection,
        token: str,
        password: str,
    ):
        get_query = """
            DELETE FROM password_tokens
            WHERE token = $1::VARCHAR AND expired_at > $2::TIMESTAMP
            RETURNING user_id
        """
        user_id = await conn.fetchval(get_query, token, utc_now())
        if user_id is None:
            raise TokenNotFound()

        update_query = """
            UPDATE users
            SET password = $1::VARCHAR
            WHERE user_id = $2::UUID
        """
        await conn.execute(update_query, password, user_id)
