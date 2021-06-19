"""Add users table

Revision ID: 3343d6cd2589
Revises:
Create Date: 2021-06-07 22:45:39.222347

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import VARCHAR
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from auth_service.db.models import role_enum

# revision identifiers, used by Alembic.
revision = "3343d6cd2589"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    role_enum.create(op.get_bind())
    op.create_table(
        "users",
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("name", VARCHAR(128), nullable=False),
        sa.Column("email", VARCHAR(128), nullable=False),
        sa.Column("password", VARCHAR(128), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("verified_at", TIMESTAMP, nullable=False),
        sa.Column("role", role_enum, nullable=False),

        sa.PrimaryKeyConstraint("user_id")
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE role_enum")
