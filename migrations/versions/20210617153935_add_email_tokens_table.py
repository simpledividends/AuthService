"""add_email_tokens_table

Revision ID: 57e71c68b430
Revises: 479e659114ca
Create Date: 2021-06-17 15:39:35.502867

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import VARCHAR
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = '57e71c68b430'
down_revision = '479e659114ca'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_tokens",
        sa.Column("token", VARCHAR(64), nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("email", VARCHAR(128), nullable=False),
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
    op.drop_table("email_tokens")
