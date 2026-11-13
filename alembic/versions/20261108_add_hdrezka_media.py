"""Store per-user HDRezka media IDs."""

from alembic import op
import sqlalchemy as sa

revision = '20261108_hdrezka_media'
down_revision = '20261108_hdrezka_cookies'


def upgrade():
  op.create_table(
    'hdrezka_media',
    sa.Column('uid', sa.String(32), primary_key=True),
    sa.Column('owner_uid', sa.String(6), sa.ForeignKey('users.uid'), nullable=False),
    sa.Column('path', sa.String(1024), nullable=False),
    sa.Column('upstream_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(16), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
  )
  op.create_index('ix_hdrezka_media_owner_uid', 'hdrezka_media', ['owner_uid'])


def downgrade():
  op.drop_index('ix_hdrezka_media_owner_uid', table_name='hdrezka_media')
  op.drop_table('hdrezka_media')
