import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import logging
import re
from secrets import token_urlsafe
from time import time
from urllib.parse import unquote, urlsplit

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import SQLAlchemyError

from src.exceptions import JSRError
from src.models import DownloadSource
from .hdrezka import group_download_streams


_VIDEO_EXPIRY = re.compile(r':([0-9]{10}):')
_VIDEO_ZONE = timezone(timedelta(hours=3))
_UID = re.compile(r'[A-Za-z0-9_-]{14}')


def source_expiry(url, entity_type):
  try:
    parts = urlsplit(url)
    path = unquote(parts.path)
    if entity_type == 'video':
      match = _VIDEO_EXPIRY.search(path + '?' + unquote(parts.query))
      if match:
        return int(datetime.strptime(match[1], '%Y%m%d%H').replace(tzinfo=_VIDEO_ZONE).timestamp())
    else:
      segment = path.strip('/').split('/')[-9]
      if re.fullmatch(r'[0-9]{1,12}', segment):
        return int(segment)
  except (ValueError, IndexError):
    pass
  return None


async def cached_sources(session, user_uid, media_uid, translator_id, season, episode):
  now = time()
  active = or_(DownloadSource.expires_at > now, DownloadSource.reserve_expires_at > now)
  selection = (
    DownloadSource.user_uid == user_uid,
    DownloadSource.media_uid == media_uid,
    DownloadSource.translator_id == translator_id,
    DownloadSource.season == season,
    DownloadSource.episode == episode,
  )
  batch = (
    select(DownloadSource.batch_uid)
    .where(*selection, DownloadSource.entity_type == 'video', active)
    .order_by(DownloadSource.created_at.desc(), DownloadSource.batch_uid.desc())
    .limit(1)
    .scalar_subquery()
  )
  query = (
    select(DownloadSource.uid, DownloadSource.title, DownloadSource.entity_type)
    .where(*selection, DownloadSource.batch_uid == batch, active)
    .order_by(DownloadSource.position)
  )
  response = {'streams': [], 'subtitles': []}
  for uid, title, entity_type in await session.execute(query):
    key = 'streams' if entity_type == 'video' else 'subtitles'
    response[key].append({'uid': uid, 'title': title})
  return response if response['streams'] else None


def save_sources(session, result, user_uid, media_uid, translator_id, season, episode, allowed_url):
  batch_uid = token_urlsafe(11)[:14]
  now = time()
  groups = {'streams': {}, 'subtitles': {}}
  for stream in group_download_streams(result['streams']).values():
    groups['streams'][stream['title']] = [stream['url'], stream['reserve']]
  for track in result['subtitles']:
    groups['subtitles'].setdefault(track['language'], []).append(track['url'])

  response = {}
  for key, options in groups.items():
    entity_type = 'video' if key == 'streams' else 'subtitles'
    response[key] = []
    for title, links in options.items():
      candidates = []
      for url in dict.fromkeys(links):
        if url is not None and allowed_url(url) is not None:
          expires = source_expiry(url, entity_type)
          if expires is not None and expires > now:
            candidates.append((url, expires))
      if not candidates:
        continue
      url, expires_at = candidates[0]
      reserve, reserve_expires_at = candidates[1] if len(candidates) > 1 else (None, None)
      uid = token_urlsafe(11)[:14]
      session.add(DownloadSource(
        uid=uid, user_uid=user_uid, media_uid=media_uid, batch_uid=batch_uid,
        entity_type=entity_type, title=title, url=url, reserve=reserve,
        expires_at=expires_at, reserve_expires_at=reserve_expires_at,
        translator_id=translator_id, position=len(response[key]), season=season, episode=episode,
      ))
      response[key].append({'uid': uid, 'title': title})
  if not response['streams']:
    raise JSRError('upstream_error', message='HDRezka returned no valid video sources')
  return response


async def find_source(session, uid, user_uid, media_uid, entity_type):
  if not isinstance(uid, str) or not _UID.fullmatch(uid):
    raise JSRError('invalid_payload')
  source = await DownloadSource.first(
    session, uid=uid, user_uid=user_uid, media_uid=media_uid, entity_type=entity_type,
  )
  if source is None:
    raise JSRError('not_found', message='Download source not found')
  now = time()
  if source.expires_at <= now and (source.reserve_expires_at or 0) <= now:
    raise JSRError('source_expired')
  return source


async def purge_sources(session_factory):
  async with session_factory.begin() as session:
    now = int(time())
    await session.execute(delete(DownloadSource).where(
      DownloadSource.expires_at <= now,
      or_(DownloadSource.reserve_expires_at.is_(None), DownloadSource.reserve_expires_at <= now),
    ))


async def source_cleanup_ctx(app):
  session_factory = app['db_sessionmaker']
  await purge_sources(session_factory)

  async def cleanup():
    while True:
      await asyncio.sleep(3600)
      try:
        await purge_sources(session_factory)
      except SQLAlchemyError:
        logging.error('Download source cleanup failed')

  task = asyncio.create_task(cleanup())
  try:
    yield
  finally:
    task.cancel()
    with suppress(asyncio.CancelledError):
      await task
