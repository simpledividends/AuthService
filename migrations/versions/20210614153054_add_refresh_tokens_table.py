"""add_refresh_tokens_table

Revision ID: 479e659114ca
Revises: fec3f53dcd7f
Create Date: 2021-06-14 15:30:54.509963

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import VARCHAR
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = "479e659114ca"
down_revision = "fec3f53dcd7f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refresh_tokens",
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
        op.f("ix_refresh_session_id"),
        "refresh_tokens",
        ["session_id"],
        unique=True
    )


def downgrade():
    op.drop_index(op.f("ix_refresh_session_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
