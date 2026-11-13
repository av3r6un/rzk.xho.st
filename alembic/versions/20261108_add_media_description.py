"""Cache media descriptions."""

from alembic import op
import sqlalchemy as sa


revision = '20261108_media_description'
down_revision = '20261108_media_cache'


def upgrade():
  op.add_column('media', sa.Column('description', sa.Text(), nullable=True))


def downgrade():
  with op.batch_alter_table('media') as batch:
    batch.drop_column('description')
