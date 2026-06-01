"""add country to person

Revision ID: b1f3c7d29e84
Revises: e7a4c2b9f1d3
Create Date: 2026-06-01 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b1f3c7d29e84"
down_revision = "e7a4c2b9f1d3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("person", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("country", sa.String(length=2), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("person", schema=None) as batch_op:
        batch_op.drop_column("country")
