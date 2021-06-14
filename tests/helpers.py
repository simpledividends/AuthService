import typing as tp
from datetime import datetime, timedelta
from http import HTTPStatus
from uuid import UUID, uuid4

import orjson
import werkzeug
from sqlalchemy import inspect, orm
from sqlalchemy.sql import text

from auth_service.db.models import (
    AccessTokenTable,
    Base,
    NewcomerTable,
    RefreshTokenTable,
    RegistrationTokenTable,
    SessionTable,
    UserTable,
)
from auth_service.models.auth import TokenPair
from auth_service.models.user import UserRole
from auth_service.security import SecurityService
from auth_service.utils import utc_now

DBObjectCreator = tp.Callable[[Base], None]


class FakeMailgunServer:

    def __init__(self) -> None:
        self.requests: tp.List[werkzeug.Request] = []
        self.return_error = False

    def set_return_error(self, return_error: bool) -> None:
        self.return_error = return_error

    def handle_send_mail_request(
        self,
        request: werkzeug.Request,
    ) -> werkzeug.Response:
        self.requests.append(request)
        if self.return_error:
            return werkzeug.Response(
                orjson.dumps({"error": "some error"}),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                content_type="application/json"
            )
        return werkzeug.Response(
            orjson.dumps({"message": "ok"}),
            status=HTTPStatus.OK,
            content_type="application/json"
        )


def assert_all_tables_are_empty(
    db_session: orm.Session,
    exclude: tp.Collection[Base] = (),
) -> None:
    inspector = inspect(db_session.get_bind())
    tables_all = inspector.get_table_names()
    exclude_names = [e.__tablename__ for e in exclude]
    tables = set(tables_all) - (set(exclude_names) | {"alembic_version"})
    for table in tables:
        request = text(f"SELECT COUNT(*) FROM {table}")
        count = db_session.execute(request).fetchone()[0]
        assert count == 0


def make_db_user(
    user_id: tp.Optional[UUID] = None,
    name: str = "user name",
    email: str = "simple@dividends.ru",
    password: str = "hashed_pass",
    created_at: datetime = datetime(2021, 6, 12),
    verified_at: datetime = datetime(2021, 6, 13),
    role: UserRole = UserRole.user,
) -> UserTable:
    return UserTable(
        user_id=str(user_id or uuid4()),
        name=name,
        email=email,
        password=password,
        created_at=created_at,
        verified_at=verified_at,
        role=role,
    )


def make_db_newcomer(
    user_id: tp.Optional[UUID] = None,
    name: str = "user name",
    email: str = "simple@dividends.ru",
    password: str = "hashed_pass",
    created_at: datetime = datetime(2021, 6, 12),
) -> NewcomerTable:
    return NewcomerTable(
        user_id=str(user_id or uuid4()),
        name=name,
        email=email,
        password=password,
        created_at=created_at,
    )


def make_db_registration_token(
    token: str,
    user_id: tp.Optional[UUID] = None,
    created_at: datetime = datetime(2021, 6, 12),
    expired_at: tp.Optional[datetime] = None,
) -> RegistrationTokenTable:
    return RegistrationTokenTable(
        token=token,
        user_id=str(user_id or uuid4()),
        created_at=created_at,
        expired_at=expired_at or utc_now() + timedelta(days=10),
    )


def make_db_session(
    session_id: tp.Optional[UUID] = None,
    user_id: tp.Optional[UUID] = None,
    started_at: datetime = datetime(2021, 6, 12),
    finished_at: tp.Optional[datetime] = None,
) -> SessionTable:
    return SessionTable(
        session_id=str(session_id or uuid4()),
        user_id=str(user_id or uuid4()),
        started_at=started_at,
        finished_at=finished_at,
    )


def make_access_token(
    token: str,
    session_id: tp.Optional[UUID] = None,
    created_at: datetime = datetime(2021, 6, 12),
    expired_at: tp.Optional[datetime] = None,
) -> AccessTokenTable:
    return AccessTokenTable(
        token=token,
        session_id=str(session_id or uuid4()),
        created_at=created_at,
        expired_at=expired_at or utc_now() + timedelta(days=10),
    )


def make_refresh_token(
    token: str,
    session_id: tp.Optional[UUID] = None,
    created_at: datetime = datetime(2021, 6, 12),
    expired_at: tp.Optional[datetime] = None,
) -> RefreshTokenTable:
    return RefreshTokenTable(
        token=token,
        session_id=str(session_id or uuid4()),
        created_at=created_at,
        expired_at=expired_at or utc_now() + timedelta(days=10),
    )


def create_authorized_user(
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
) -> tp.Tuple[UUID, TokenPair]:
    user = make_db_user()
    session = make_db_session(user_id=user.user_id)
    a_token_string, a_token = security_service.make_access_token(uuid4())
    r_token_string, r_token = security_service.make_refresh_token(uuid4())
    access_token = make_access_token(
        token=a_token.token,
        session_id=session.session_id,
    )
    refresh_token = make_refresh_token(
        token=r_token.token,
        session_id=session.session_id,
    )
    for obj in (user, session, access_token, refresh_token):
        create_db_object(obj)

    return (
        user.user_id,
        TokenPair(access_token=a_token_string, refresh_token=r_token_string),
    )
