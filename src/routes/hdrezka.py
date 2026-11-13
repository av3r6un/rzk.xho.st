from json import JSONDecodeError
import re

from aiohttp.web import Request, RouteTableDef, json_response

from src.exceptions import JSRError
from src.services.downloads import DOWNLOADS
from src.services.download_sources import cached_sources, find_source, save_sources
from src.services.hdrezka import get_streams
from src.services.media_search import MediaSearchService


hdrezka = RouteTableDef()
_cookie_pair = re.compile(
  r"[!#$%&'*+\-.^_\x60|~0-9A-Za-z]+="
  r'(?:[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*'
  r'|"[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*")'
)


@hdrezka.get('/api/rezka/cookies')
async def get_cookies(req: Request, *args, **kwargs):
  return {'configured': bool(req['current_user'].hdrezka_cookies)}


async def _request_data(req):
  try:
    payload = await req.json()
  except (JSONDecodeError, UnicodeError):
    raise JSRError('invalid_payload') from None
  data = payload.get('data') if isinstance(payload, dict) else None
  if not isinstance(data, dict):
    raise JSRError('invalid_payload')
  return data


@hdrezka.put('/api/rezka/cookies')
async def put_cookies(req: Request, *args, **kwargs):
  data = await _request_data(req)
  cookies = data.get('cookies')
  if not isinstance(cookies, str) or len(cookies) > 8192:
    raise JSRError('invalid_payload')

  pairs = [pair.strip(' \t') for pair in cookies.split(';')]
  if not all(_cookie_pair.fullmatch(pair) for pair in pairs):
    raise JSRError('invalid_payload')

  req['current_user'].hdrezka_cookies = '; '.join(pairs)
  return {'configured': True}


@hdrezka.delete('/api/rezka/cookies')
async def delete_cookies(req: Request, *args, **kwargs):
  req['current_user'].hdrezka_cookies = None
  return {'configured': False}


@hdrezka.post('/api/rezka/media')
async def register_media(req: Request, session):
  data = await _request_data(req)
  details, created = await MediaSearchService.search(session, req['current_user'], data.get('url'))
  return details, 201 if created else 200


async def _find_media(req, session):
  media_id = req.match_info['media_id']
  if not re.fullmatch(r'[0-9a-f]{32}', media_id):
    raise JSRError('not_found')
  return await MediaSearchService.find(session, req['current_user'].uid, media_id)


@hdrezka.get('/api/rezka/media/{media_id}')
async def media_details(req: Request, session):
  media = await _find_media(req, session)
  return await MediaSearchService.details(session, req['current_user'], media)


@hdrezka.post('/api/rezka/media/{media_id}/streams')
async def media_streams(req: Request, session):
  media = await _find_media(req, session)
  data = await _request_data(req)
  selection = _stream_selection(data, media.category)
  user = req['current_user']
  cached = await cached_sources(session, user.uid, media.uid, *selection)
  if cached is not None:
    return cached
  result = await get_streams(media, user.hdrezka_cookies, *selection)
  return save_sources(
    session, result, user.uid, media.uid, *selection,
    req.app[DOWNLOADS].allowed_url,
  )


def _stream_selection(data, category):
  translator = data.get('translator_id')
  season = data.get('season')
  episode = data.get('episode')
  if type(translator) is not int or not 0 < translator <= 999999999:
    raise JSRError('invalid_payload')
  if season is not None or episode is not None or category == 'series':
    if any(type(value) is not int or not 0 < value <= 99999 for value in (season, episode)):
      raise JSRError('invalid_payload')
  return translator, season, episode


@hdrezka.post('/api/rezka/media/{media_id}/downloads')
async def create_download(req: Request, session):
  media = await _find_media(req, session)
  data = await _request_data(req)
  user_uid = req['current_user'].uid
  video = await find_source(session, data.get('video_uid'), user_uid, media.uid, 'video')
  subtitles = None
  if data.get('subtitles_uid') is not None:
    subtitles = await find_source(
      session, data['subtitles_uid'], user_uid, media.uid, 'subtitles',
    )
    if subtitles.batch_uid != video.batch_uid:
      raise JSRError('invalid_payload', message='Choose video and subtitles from the same stream list')
  download = req.app[DOWNLOADS].issue(
    video, subtitles, media.original_name or media.name or 'video', release=media.release,
  )
  return json_response(
    {'status': 'success', 'body': download}, status=201,
    headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'},
  )


@hdrezka.get('/api/rezka/downloads/{ticket}/video', name='download_video', allow_head=False)
async def download_video(req: Request, session=None):
  return await req.app[DOWNLOADS].transfer(req, video=True)


@hdrezka.get('/api/rezka/downloads/{ticket}/subtitles', name='download_subtitles', allow_head=False)
async def download_subtitles(req: Request, session=None):
  return await req.app[DOWNLOADS].transfer(req, video=False)


@hdrezka.get('/api/rezka/downloads/{ticket}/mp4', name='download_mp4', allow_head=False)
async def download_mp4(req: Request):
  return await req.app[DOWNLOADS].mp4.transfer(req)


@hdrezka.get('/api/rezka/downloads/{ticket}/prepare', name='prepare_mp4', allow_head=False)
async def prepare_mp4(req: Request):
  return await req.app[DOWNLOADS].prepare_merged(req)
