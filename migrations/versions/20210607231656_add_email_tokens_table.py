"""Add email_tokens table

Revision ID: 57175ede5e63
Revises: 3343d6cd2589
Create Date: 2021-06-07 23:16:56.345900

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import VARCHAR
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

revision = '57175ede5e63'
down_revision = '3343d6cd2589'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'email_tokens',
        sa.Column("token", VARCHAR(64), nullable=False),
        sa.Column('user_id', UUID, nullable=False),
        sa.Column("email", VARCHAR(128), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("expired_at", TIMESTAMP, nullable=False),

        sa.PrimaryKeyConstraint('token'),
        sa.ForeignKeyConstraint(
            columns=('user_id',),
            refcolumns=('users.user_id',),
            ondelete='CASCADE',
        ),
    )
    op.create_index(
        op.f('ix_email_tokens_email'),
        'email_tokens',
        ['email'],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_email_tokens_email'), table_name='email_tokens')
    op.drop_table('email_tokens')
