import asyncio

from aiohttp.web import Request, Response, RouteTableDef, json_response

from src.exceptions import JSRError
from src.services.hdrezka import get_streams
from src.services.media_search import MediaSearchService
from src.services.watch import WATCH, playlist_response


watch = RouteTableDef()
_NO_STORE = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'}


def selection(request, category):
  values = []
  for key in ('t', 's', 'e'):
    value = request['params'].get(key)
    if value is None:
      values.append(None)
    elif isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 9:
      values.append(int(value))
    else:
      raise JSRError('invalid_payload')
  translator, season, episode = values
  if not translator or (season is None) != (episode is None):
    raise JSRError('invalid_payload')
  if season == 0 or episode == 0 or (category == 'series' and season is None):
    raise JSRError('invalid_payload')
  return translator, season, episode


async def watch_sources(req, session):
  user = req['current_user']
  media = await MediaSearchService.find_media(session, req.match_info['media_uid'], user.uid)
  return await get_streams(media, user.hdrezka_cookies, *selection(req, media.category))


@watch.get('/api/watch/{media_uid}', name='create_watch', allow_head=False)
async def create_watch(req: Request, session):
  sources = await watch_sources(req, session)
  body = req.app[WATCH].issue_files(sources)
  return json_response({'status': 'success', 'body': body}, status=201, headers=_NO_STORE)


@watch.get('/api/watch/{media_uid}/share', name='create_watch_share', allow_head=False)
async def create_watch_share(req: Request, session):
  sources = await watch_sources(req, session)
  try:
    async with asyncio.timeout(40):
      body = await req.app[WATCH].issue(sources)
  except TimeoutError:
    raise JSRError('upstream_error', message='CDN timed out while preparing HLS playback') from None
  return json_response({'status': 'success', 'body': body}, status=201, headers=_NO_STORE)


@watch.get('/api/watch/session/{ticket}/master.m3u8', name='watch_master')
async def watch_master(req: Request):
  master = req.app[WATCH].get(req.match_info['ticket']).master
  if not master:
    raise JSRError('not_found', message='Watch master playlist not found')
  return playlist_response(master)


@watch.get('/api/watch/session/{ticket}/{path:.+}', name='watch_asset')
async def watch_asset(req: Request):
  service = req.app[WATCH]
  session = service.get(req.match_info['ticket'])
  path = req.match_info['path']
  if path in session.files:
    candidates, video = session.files[path]
    return await service.cdn.transfer_resource(req, candidates, video=video)
  if path in session.playlists:
    return playlist_response(session.playlists[path])
  if path in session.subtitles:
    return Response(text=session.subtitles[path], content_type='text/vtt', headers=_NO_STORE)
  if path in session.media:
    return await service.transfer(req, *session.media[path])
  raise JSRError('not_found', message='Watch resource not found')
