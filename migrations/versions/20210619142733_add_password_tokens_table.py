"""add_password_tokens_table

Revision ID: 73dbc24c972f
Revises: 57e71c68b430
Create Date: 2021-06-19 14:27:33.171572

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import VARCHAR
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = '73dbc24c972f'
down_revision = '57e71c68b430'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "password_tokens",
        sa.Column("token", VARCHAR(64), nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("expired_at", TIMESTAMP, nullable=False),

        sa.PrimaryKeyConstraint("token"),
        sa.ForeignKeyConstraint(
            columns=("user_id",),
            refcolumns=("users.user_id",),
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("password_tokens")
