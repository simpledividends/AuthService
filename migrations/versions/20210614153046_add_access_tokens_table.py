"""add_access_tokens_table

Revision ID: fec3f53dcd7f
Revises: 05d0c2f3267a
Create Date: 2021-06-14 15:30:46.530827

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import VARCHAR
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = "fec3f53dcd7f"
down_revision = "05d0c2f3267a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "access_tokens",
        sa.Column("token", VARCHAR(64), nullable=False),
        sa.Column("session_id", UUID, nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("expired_at", TIMESTAMP, nullable=False),

        sa.PrimaryKeyConstraint("token"),
        sa.ForeignKeyConstraint(
            columns=("session_id",),
            refcolumns=("sessions.session_id",),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_access_session_id"),
        "access_tokens",
        ["session_id"],
        unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_access_session_id"), table_name="access_tokens")
    op.drop_table("access_tokens")
