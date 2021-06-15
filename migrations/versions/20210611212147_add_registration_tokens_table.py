"""add_registration_tokens_table

Revision ID: c3522116d928
Revises: 7a05b5faf3eb
Create Date: 2021-06-11 21:21:47.140763

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import VARCHAR
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = "c3522116d928"
down_revision = "7a05b5faf3eb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "registration_tokens",
        sa.Column("token", VARCHAR(64), nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("expired_at", TIMESTAMP, nullable=False),

        sa.PrimaryKeyConstraint("token"),
        sa.ForeignKeyConstraint(
            columns=("user_id",),
            refcolumns=("newcomers.user_id",),
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("registration_tokens")
