import typing as tp
from datetime import datetime, timedelta
from http import HTTPStatus
from uuid import UUID, uuid4

import orjson
import werkzeug
from sqlalchemy import inspect, orm
from sqlalchemy.sql import text
from starlette.testclient import TestClient

from auth_service.db.models import (
    AccessTokenTable,
    Base,
    EmailTokenTable,
    NewcomerTable,
    PasswordTokenTable,
    RefreshTokenTable,
    RegistrationTokenTable,
    SessionTable,
    UserTable,
)
from auth_service.models.user import UserRole
from auth_service.security import SecurityService
from auth_service.utils import utc_now

from .utils import random_email

DBObjectCreator = tp.Callable[[Base], None]


class FakeSendgridServer:

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
            "",
            status=HTTPStatus.ACCEPTED,
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
    email: tp.Optional[str] = None,
    password: str = "hashed_pass",
    created_at: datetime = datetime(2021, 6, 12),
    verified_at: datetime = datetime(2021, 6, 13),
    role: UserRole = UserRole.user,
) -> UserTable:
    return UserTable(
        user_id=str(user_id or uuid4()),
        name=name,
        email=email or random_email(),
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
    token: str = "hashed_token",
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


def make_email_token(
    token: str = "hashed_token",
    user_id: tp.Optional[UUID] = None,
    email: str = "some@mail.ru",
    created_at: datetime = datetime(2021, 6, 12),
    expired_at: tp.Optional[datetime] = None,
) -> EmailTokenTable:
    return EmailTokenTable(
        token=token,
        user_id=str(user_id or uuid4()),
        email=email,
        created_at=created_at,
        expired_at=expired_at or utc_now() + timedelta(days=10),
    )


def make_password_token(
    token: str = "hashed_token",
    user_id: tp.Optional[UUID] = None,
    created_at: datetime = datetime(2021, 6, 12),
    expired_at: tp.Optional[datetime] = None,
) -> EmailTokenTable:
    return PasswordTokenTable(
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
    user_role: UserRole = UserRole.user,
    token_expired_at: tp.Optional[datetime] = None,
    hashed_password: str = "hashed_password"
) -> tp.Tuple[UserTable, str]:
    user = make_db_user(role=user_role, password=hashed_password)
    session = make_db_session(user_id=user.user_id)
    token_string, token = security_service.make_access_token(uuid4())
    token_db = make_access_token(
        token=token.token,
        session_id=session.session_id,
        expired_at=token_expired_at,
    )
    for obj in (user, session, token_db):
        create_db_object(obj)

    return user, token_string


def check_access_forbidden(
    client: TestClient,
    security_service: SecurityService,
    create_db_object: DBObjectCreator,
    request_params: tp.Dict[str, tp.Any],
    expected_status: HTTPStatus = HTTPStatus.FORBIDDEN,
) -> None:
    cases = (
        ("NotAuthorization", "Bearer ", None, "authorization.not_set"),
        ("Authorization", "Bearer", None, "authorization.scheme_unrecognised"),
        ("Authorization", "NotBearer ", None, "authorization.scheme_invalid"),
        ("Authorization", "Bearer ", "incorrect_token", "forbidden"),
        ("Authorization", "Bearer ", "expired_token", "forbidden"),
    )

    for key, value_beginning, token, expected_error_key in cases:
        if token == "expired_token":
            token_expired_at = utc_now() - timedelta(seconds=1)
            token = None
        else:
            token_expired_at = utc_now() + timedelta(hours=1)

        _, access_token = create_authorized_user(
            security_service,
            create_db_object,
            token_expired_at=token_expired_at,
        )
        token = token or access_token

        with client:
            resp = client.request(
                **request_params,
                headers={key: value_beginning + token}
            )

        assert resp.status_code == expected_status
        if expected_status == HTTPStatus.FORBIDDEN:
            assert resp.json()["errors"][0]["error_key"] == expected_error_key
