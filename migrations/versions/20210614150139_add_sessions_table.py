"""add_sessions_table

Revision ID: 05d0c2f3267a
Revises: c3522116d928
Create Date: 2021-06-14 15:01:39.108107

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

# revision identifiers, used by Alembic.

revision = "05d0c2f3267a"
down_revision = "c3522116d928"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sessions",
        sa.Column("session_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("started_at", TIMESTAMP, nullable=False),
        sa.Column("finished_at", TIMESTAMP, nullable=True),

        sa.PrimaryKeyConstraint("session_id"),
        sa.ForeignKeyConstraint(
            columns=("user_id",),
            refcolumns=("users.user_id",),
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("sessions")
