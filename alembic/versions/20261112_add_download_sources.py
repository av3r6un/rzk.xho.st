from alembic import op
import sqlalchemy as sa


revision = '20261112_download_sources'
down_revision = '16fc6af848f2'
branch_labels = None
depends_on = None


def upgrade():
  op.create_table(
    'download_sources',
    sa.Column('uid', sa.String(14), primary_key=True),
    sa.Column('user_uid', sa.String(6), sa.ForeignKey('users.uid', ondelete='CASCADE'), nullable=False),
    sa.Column('media_uid', sa.String(32), sa.ForeignKey('media.uid', ondelete='CASCADE'), nullable=False),
    sa.Column('batch_uid', sa.String(14), nullable=False),
    sa.Column('entity_type', sa.String(9), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('reserve', sa.Text()),
    sa.Column('expires_at', sa.BigInteger(), nullable=False),
    sa.Column('reserve_expires_at', sa.BigInteger()),
    sa.Column('season', sa.Integer()),
    sa.Column('episode', sa.Integer()),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
  )
  op.create_index('ix_download_sources_expires_at', 'download_sources', ['expires_at'])


def downgrade():
  op.drop_index('ix_download_sources_expires_at', table_name='download_sources')
  op.drop_table('download_sources')
