from alembic import op
import sqlalchemy as sa


revision = '20261115_active_encoders'
down_revision = '20261112_cache_sources'


def upgrade():
  op.create_table(
    'active_encoders',
    sa.Column('name', sa.String(64), primary_key=True),
    sa.Column('available', sa.Boolean()),
    sa.Column('working', sa.Boolean()),
    sa.Column('checked_at', sa.BigInteger()),
    sa.Column('error', sa.String(512)),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
  )


def downgrade():
  op.drop_table('active_encoders')
