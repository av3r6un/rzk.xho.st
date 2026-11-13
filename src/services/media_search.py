from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from src.exceptions import JSRError
from src.models import Media, MediaTranslator, SearchHistory, Translator
from .hdrezka import ORIGIN, get_media_details, parse_media_url


_DETAIL_FIELDS = ('name', 'original_name', 'cover', 'slogan', 'description', 'release', 'country', 'genres')


class MediaSearchService:
  @classmethod
  async def search(cls, session, user, url):
    path, rezka_id, category = parse_media_url(url)
    media = await Media.first(session, id=rezka_id)
    created = False
    page_details = None
    if media is None:
      candidate = Media(uid=uuid4().hex, id=rezka_id, path=path, category=category)
      page_details = await get_media_details(candidate, user.hdrezka_cookies)
      cls._set_details(candidate, page_details)
      media, created = await cls._get_or_insert(session, candidate, id=rezka_id)
      if created:
        await cls._save_translators(session, media, page_details['translators'])

    history, added = await cls._get_or_insert(
      session, SearchHistory(user_uid=user.uid, media_uid=media.uid),
      user_uid=user.uid, media_uid=media.uid,
    )
    if not added:
      await session.execute(
        update(SearchHistory).where(SearchHistory.id == history.id).values(updated_at=func.now()),
      )
    return await cls.details(session, user, media, page_details), created

  @staticmethod
  async def find(session, user_uid, media_uid):
    query = (
      select(Media)
      .join(SearchHistory, SearchHistory.media_uid == Media.uid)
      .where(SearchHistory.user_uid == user_uid, SearchHistory.media_uid == media_uid)
    )
    media = await session.scalar(query)
    if media is None:
      raise JSRError('not_found')
    return media

  @classmethod
  async def details(cls, session, user, media, page_details=None):
    # NULL means the description has not been fetched, while an empty string means it was absent.
    needs_metadata = media.name is None or media.description is None
    needs_page = needs_metadata or media.external_ids is None or media.category != 'films'
    if page_details is None and needs_page:
      page_details = await get_media_details(media, user.hdrezka_cookies)
    if needs_metadata:
      cls._set_details(media, page_details)
      await cls._save_translators(session, media, page_details['translators'])
    if page_details is not None and media.external_ids != page_details['external_ids']:
      media.external_ids = page_details['external_ids']

    external_ids = media.external_ids or {}
    query = (
      select(Translator)
      .join(MediaTranslator, MediaTranslator.translator_uid == Translator.uid)
      .where(MediaTranslator.media_uid == media.uid)
      .order_by(MediaTranslator.id)
    )
    translators = (await session.scalars(query)).all()
    return {
      'id': media.id,
      'uid': media.uid,
      'category': media.category,
      'url': ORIGIN + media.path,
      **{field: getattr(media, field) for field in _DETAIL_FIELDS},
      'description': media.description or None,
      'external_ids': media.external_ids,
      'seasons': page_details['seasons'] if page_details else [],
      'translators': [
        {'id': translator.id, 'title': translator.name}
        for translator in translators
      ],
    }

  @staticmethod
  def _set_details(media, details):
    for field in _DETAIL_FIELDS:
      setattr(media, field, details[field])
    media.external_ids = details['external_ids']

  @classmethod
  async def _save_translators(cls, session, media, translators):
    # Acquire translator uniqueness constraints in a consistent order.
    for item in sorted(translators, key=lambda item: item['id']):
      translator, _ = await cls._get_or_insert(
        session, Translator(uid=uuid4().hex[:10], id=item['id'], name=item['title']), id=item['id'],
      )
      if translator.name is None and item['title'] is not None:
        translator.name = item['title']
      await cls._get_or_insert(
        session, MediaTranslator(media.uid, translator.uid),
        media_uid=media.uid, translator_uid=translator.uid,
      )

  @staticmethod
  async def _get_or_insert(session, candidate, **key):
    model = type(candidate)
    existing = await model.first(session, **key)
    if existing is not None:
      return existing, False
    try:
      async with session.begin_nested():
        session.add(candidate)
        await session.flush()
    except IntegrityError:
      existing = await model.first(session, **key)
      if existing is None:
        raise
      return existing, False
    return candidate, True
