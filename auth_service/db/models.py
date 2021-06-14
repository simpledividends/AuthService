from sqlalchemy import Column, ForeignKey, orm
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base

from auth_service.models.user import UserRole
from auth_service.utils import utc_now

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
