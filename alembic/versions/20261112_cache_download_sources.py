from alembic import op
import sqlalchemy as sa


revision = '20261112_cache_sources'
down_revision = '20261112_download_sources'
branch_labels = None
depends_on = None


def upgrade():
  op.add_column('download_sources', sa.Column('translator_id', sa.Integer()))
  op.add_column('download_sources', sa.Column('position', sa.Integer()))
  op.create_index(
    'ix_download_sources_selection', 'download_sources',
    ['user_uid', 'media_uid', 'translator_id', 'season', 'episode'],
  )


def downgrade():
  op.drop_index('ix_download_sources_selection', table_name='download_sources')
  op.drop_column('download_sources', 'position')
  op.drop_column('download_sources', 'translator_id')
