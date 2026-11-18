from src.services.download_sources import cached_sources, find_source, save_sources, stream_selection
from aiohttp.web import Request, RouteTableDef, json_response
from src.services.media_search import MediaSearchService
from src.services.downloads import DOWNLOADS
from src.services.hdrezka import get_streams
from src.exceptions import JSRError


hdrezka = RouteTableDef()


@hdrezka.get('/api/rezka/cookies')
async def get_cookies(req: Request, *args, **kwargs):
  return {'configured': bool(req['current_user'].hdrezka_cookies)}


@hdrezka.put('/api/rezka/cookies')
async def put_cookies(req: Request, *args, **kwargs):
  cookies = req['request_data'].get('cookies')
  if not isinstance(cookies, str) or len(cookies) > 8192:
    raise JSRError('invalid_payload')

  req['current_user'].cookies = cookies

  return {'configured': True}


@hdrezka.delete('/api/rezka/cookies')
async def delete_cookies(req: Request, *args, **kwargs):
  req['current_user'].hdrezka_cookies = None
  return {'configured': False}


@hdrezka.post('/api/rezka/media')
async def register_media(req: Request, session):
  data = req['request_data']
  details, created = await MediaSearchService.search(session, req['current_user'], data.get('url'))
  return details, 201 if created else 200


@hdrezka.get('/api/rezka/media/{media_id}')
async def media_details(req: Request, session):
  media = await MediaSearchService.find_media(session, req.match_info['media_id'], req['current_user'].uid)
  return await MediaSearchService.details(session, req['current_user'], media)


@hdrezka.post('/api/rezka/media/{media_id}/streams')
async def media_streams(req: Request, session):
  media = await MediaSearchService.find_media(session, req.match_info['media_id'], req['current_user'].uid)
  data = req['request_data']
  selection = stream_selection(media.category, **data)
  user = req['current_user']
  cached = await cached_sources(session, user.uid, media.uid, *selection)
  if cached is not None:
    return cached
  result = await get_streams(media, user.hdrezka_cookies, *selection)
  return save_sources(
    session, result, user.uid, media.uid, *selection,
    req.app[DOWNLOADS].allowed_url,
  )


@hdrezka.post('/api/rezka/media/{media_id}/downloads')
async def create_download(req: Request, session):
  media = await MediaSearchService.find_media(session, req.match_info['media_id'], req['current_user'].uid)
  data = req['request_data']
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
