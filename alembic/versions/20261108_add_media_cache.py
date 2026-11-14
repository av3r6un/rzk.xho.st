"""Share media metadata and store per-user search history."""

from alembic import op
import sqlalchemy as sa


revision = '20261108_media_cache'
down_revision = '20261108_hdrezka_media'


def timestamps():
  return (
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
  )


def upgrade():
  connection = op.get_bind()
  legacy = sa.table(
    'hdrezka_media', sa.column('uid'), sa.column('owner_uid'),
    sa.column('upstream_id'), sa.column('created_at', sa.DateTime()),
  )
  rows = connection.execute(
    sa.select(legacy).order_by(legacy.c.created_at, legacy.c.uid),
  ).mappings().all()
  canonical = {}
  searches = {}
  for row in rows:
    media_uid = canonical.setdefault(row['upstream_id'], row['uid'])
    searches.setdefault((row['owner_uid'], media_uid), {
      'user_uid': row['owner_uid'], 'media_uid': media_uid, 'created_at': row['created_at'],
    })
    if row['uid'] != media_uid:
      connection.execute(legacy.delete().where(legacy.c.uid == row['uid']))

  if connection.dialect.name in {'mysql', 'mariadb'}:
    for foreign_key in sa.inspect(connection).get_foreign_keys('hdrezka_media'):
      if foreign_key['constrained_columns'] == ['owner_uid']:
        op.drop_constraint(foreign_key['name'], 'hdrezka_media', type_='foreignkey')

  with op.batch_alter_table('hdrezka_media') as batch:
    batch.drop_index('ix_hdrezka_media_owner_uid')
    batch.drop_column('owner_uid')
    batch.alter_column(
      'upstream_id', new_column_name='id', existing_type=sa.Integer(), existing_nullable=False,
    )
    batch.add_column(sa.Column('name', sa.String(150)))
    batch.add_column(sa.Column('original_name', sa.String(255)))
    batch.add_column(sa.Column('cover', sa.String(255)))
    batch.add_column(sa.Column('slogan', sa.String(100)))
    batch.add_column(sa.Column('release', sa.Integer()))
    batch.add_column(sa.Column('country', sa.String(100)))
    batch.add_column(sa.Column('genres', sa.JSON()))
  op.rename_table('hdrezka_media', 'media')
  op.create_index('ix_media_id', 'media', ['id'], unique=True)

  search_table = op.create_table(
    'search_history',
    sa.Column('id', sa.Integer(), primary_key=True),
    sa.Column('user_uid', sa.String(6), sa.ForeignKey('users.uid'), nullable=False),
    sa.Column('media_uid', sa.String(32), sa.ForeignKey('media.uid'), nullable=False),
    sa.UniqueConstraint('user_uid', 'media_uid'),
    *timestamps(),
  )
  if searches:
    op.bulk_insert(search_table, list(searches.values()))

  op.create_table(
    'translators',
    sa.Column('uid', sa.String(10), primary_key=True),
    sa.Column('id', sa.Integer(), nullable=False, unique=True),
    sa.Column('name', sa.String(50)),
    *timestamps(),
  )
  op.create_table(
    'media_translators',
    sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column('media_uid', sa.String(32), sa.ForeignKey('media.uid'), nullable=False),
    sa.Column('translator_uid', sa.String(10), sa.ForeignKey('translators.uid'), nullable=False),
    sa.UniqueConstraint('media_uid', 'translator_uid'),
    *timestamps(),
  )


def downgrade():
  from uuid import uuid4

  connection = op.get_bind()
  metadata = sa.MetaData()
  media = sa.Table('media', metadata, autoload_with=connection)
  searches = sa.Table('search_history', metadata, autoload_with=connection)
  rows = connection.execute(
    sa.select(media.c.uid, media.c.id, media.c.path, media.c.category,
              searches.c.user_uid, searches.c.created_at)
    .join(searches, searches.c.media_uid == media.c.uid)
    .order_by(searches.c.created_at, searches.c.user_uid),
  ).mappings().all()
  op.drop_table('media_translators')
  op.drop_table('translators')
  op.drop_table('search_history')
  op.drop_table('media')
  legacy = op.create_table(
    'hdrezka_media',
    sa.Column('uid', sa.String(32), primary_key=True),
    sa.Column('owner_uid', sa.String(6), sa.ForeignKey('users.uid'), nullable=False),
    sa.Column('path', sa.String(1024), nullable=False),
    sa.Column('upstream_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(16), nullable=False),
    *timestamps(),
  )
  op.create_index('ix_hdrezka_media_owner_uid', 'hdrezka_media', ['owner_uid'])
  seen = set()
  for row in rows:
    uid = row['uid']
    connection.execute(legacy.insert().values(
      uid=uuid4().hex if uid in seen else uid, owner_uid=row['user_uid'],
      upstream_id=row['id'], path=row['path'], category=row['category'],
      created_at=row['created_at'],
    ))
    seen.add(uid)
