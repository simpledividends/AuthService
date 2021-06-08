from sqlalchemy import Column, ForeignKey, orm
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.dialects import postgresql as pg

from auth_service.models import UserRole, UserStatus
from auth_service.utils import utc_now

Model: DeclarativeMeta = declarative_base()


role_enum = pg.ENUM(
    *UserRole.__members__.keys(),
    name="role_enum",
    create_type=False,
)
status_enum = pg.ENUM(
    *UserStatus.__members__.keys(),
    name="status_enum",
    create_type=False,
)


class UserTable(Model):
    __tablename__ = "users"

    id = Column("user_id", pg.UUID, primary_key=True)
    name = Column(pg.VARCHAR(50), nullable=False)
    email = Column(pg.VARCHAR(128), unique=True, index=True, nullable=False)
    password = Column(pg.VARCHAR(72), nullable=False)
    created_at = Column(pg.TIMESTAMP, default=utc_now, nullable=False)
    is_verified = Column(pg.BOOLEAN, default=False, nullable=False)
    role = Column(role_enum, default="user", nullable=False)
    status = Column(status_enum, default="active", nullable=False)


class EmailTokenTable(Model):
    __tablename__ = "email_tokens"

    token = Column(pg.VARCHAR(64), primary_key=True, nullable=False)
    user_id = Column(pg.UUID, ForeignKey(UserTable.id), nullable=False)
    email = Column(pg.VARCHAR(128), index=True, nullable=False)
    created_at = Column(pg.TIMESTAMP, default=utc_now, nullable=False)
    expired_at = Column(pg.TIMESTAMP, nullable=False)

    user = orm.relationship(UserTable)
