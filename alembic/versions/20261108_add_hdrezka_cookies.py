"""Store HDRezka cookies per user."""

from alembic import op
import sqlalchemy as sa


revision = '20261108_hdrezka_cookies'
down_revision = 'b907721086f4'


def upgrade():
  op.add_column('users', sa.Column('hdrezka_cookies', sa.Text(), nullable=True))


def downgrade():
  op.drop_column('users', 'hdrezka_cookies')
