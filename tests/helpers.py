import typing as tp
from datetime import datetime
from http import HTTPStatus
from uuid import UUID, uuid4

import orjson
import werkzeug
from sqlalchemy import inspect, orm
from sqlalchemy.sql import text

from auth_service.db.models import Base, NewcomerTable, UserTable
from auth_service.models.user import UserRole


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
