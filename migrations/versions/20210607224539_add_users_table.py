"""Add users table

Revision ID: 3343d6cd2589
Revises:
Create Date: 2021-06-07 22:45:39.222347

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import VARCHAR, BOOLEAN
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

from auth_service.db import role_enum, status_enum

revision = "3343d6cd2589"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    role_enum.create(op.get_bind())
    status_enum.create(op.get_bind())
    op.create_table(
        "users",
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("name", VARCHAR(50), nullable=False),
        sa.Column("email", VARCHAR(128), nullable=False),
        sa.Column("password", VARCHAR(72), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("is_verified", BOOLEAN, nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),

        sa.PrimaryKeyConstraint("user_id")
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.execute('DROP TYPE role_enum')
    op.execute('DROP TYPE status_enum')
