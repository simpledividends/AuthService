from sqlalchemy import Column, ForeignKey, orm
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base

from auth_service.models.user import UserRole

Base: DeclarativeMeta = declarative_base()


role_enum = pg.ENUM(
    *UserRole.__members__.keys(),
    name="role_enum",
    create_type=False,
)


class UserTable(Base):
    __tablename__ = "users"

    user_id = Column(pg.UUID, primary_key=True)
    name = Column(pg.VARCHAR(128), nullable=False)
    email = Column(pg.VARCHAR(128), unique=True, index=True, nullable=False)
    password = Column(pg.VARCHAR(128), nullable=False)
    created_at = Column(pg.TIMESTAMP, nullable=False)
    verified_at = Column(pg.TIMESTAMP, nullable=False)
    role = Column(role_enum, default="user", nullable=False)


class NewcomerTable(Base):
    __tablename__ = "newcomers"

    user_id = Column(pg.UUID, primary_key=True)
    name = Column(pg.VARCHAR(128), nullable=False)
    email = Column(pg.VARCHAR(128), unique=True, index=True, nullable=False)
    password = Column(pg.VARCHAR(128), nullable=False)
    created_at = Column(pg.TIMESTAMP, nullable=False)


class RegistrationTokenTable(Base):
    __tablename__ = "registration_tokens"

    token = Column(pg.VARCHAR(64), primary_key=True)
    user_id = Column(
        pg.UUID,
        ForeignKey(NewcomerTable.user_id),
        nullable=False,
    )
    created_at = Column(pg.TIMESTAMP, nullable=False)
    expired_at = Column(pg.TIMESTAMP, nullable=False)

    user = orm.relationship(NewcomerTable)


class SessionTable(Base):
    __tablename__ = "sessions"

    session_id = Column(pg.UUID, primary_key=True)
    user_id = Column(pg.UUID, ForeignKey(UserTable.user_id), nullable=False)
    started_at = Column(pg.TIMESTAMP, nullable=False)
    finished_at = Column(pg.TIMESTAMP, nullable=True)

    user = orm.relationship(UserTable)


class AccessTokenTable(Base):
    __tablename__ = "access_tokens"

    token = Column(pg.VARCHAR(64), primary_key=True)
    session_id = Column(
        pg.UUID,
        ForeignKey(SessionTable.session_id),
        nullable=False,
    )
    created_at = Column(pg.TIMESTAMP, nullable=False)
    expired_at = Column(pg.TIMESTAMP, nullable=False)

    session = orm.relationship(SessionTable)


class RefreshTokenTable(Base):
    __tablename__ = "refresh_tokens"

    token = Column(pg.VARCHAR(64), primary_key=True)
    session_id = Column(
        pg.UUID,
        ForeignKey(SessionTable.session_id),
        nullable=False,
        unique=True
    )
    created_at = Column(pg.TIMESTAMP, nullable=False)
    expired_at = Column(pg.TIMESTAMP, nullable=False)

    session = orm.relationship(SessionTable)


class EmailTokenTable(Base):
    __tablename__ = "email_tokens"

    token = Column(pg.VARCHAR(64), primary_key=True)
    user_id = Column(
        pg.UUID,
        ForeignKey(UserTable.user_id),
        nullable=False,
    )
    email = Column(pg.VARCHAR(128), nullable=False)
    created_at = Column(pg.TIMESTAMP, nullable=False)
    expired_at = Column(pg.TIMESTAMP, nullable=False)

    user = orm.relationship(UserTable)
