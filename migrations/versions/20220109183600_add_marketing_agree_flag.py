"""add_marketing_agree_flag

Revision ID: 61c7f5ad5635
Revises: 73dbc24c972f
Create Date: 2022-01-09 18:36:00.745538

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BOOLEAN

# revision identifiers, used by Alembic.
revision = '61c7f5ad5635'
down_revision = '73dbc24c972f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "newcomers",
        sa.Column("marketing_agree", BOOLEAN, nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("marketing_agree", BOOLEAN, nullable=False),
    )


def downgrade():
    op.drop_column("newcomers", "marketing_agree")
    op.drop_column("users", "marketing_agree")
