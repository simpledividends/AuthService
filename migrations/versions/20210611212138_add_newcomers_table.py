"""add_newcomers_table

Revision ID: 7a05b5faf3eb
Revises: 3343d6cd2589
Create Date: 2021-06-11 21:21:38.405224

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import VARCHAR
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "7a05b5faf3eb"
down_revision = "3343d6cd2589"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "newcomers",
        sa.Column("user_id", pg.UUID, nullable=False),
        sa.Column("name", VARCHAR(128), nullable=False),
        sa.Column("email", VARCHAR(128), nullable=False),
        sa.Column("password", VARCHAR(128), nullable=False),
        sa.Column("created_at", pg.TIMESTAMP, nullable=False),

        sa.PrimaryKeyConstraint("user_id")
    )
    op.create_index(
        op.f("ix_newcomers_email"),
        "newcomers",
        ["email"],
        unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_newcomers_email"), table_name="newcomers")
    op.drop_table("newcomers")
