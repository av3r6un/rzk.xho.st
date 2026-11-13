from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
import re
from secrets import token_urlsafe
from time import monotonic, time
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout, DummyCookieJar, TCPConnector
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import ThreadedResolver
from aiohttp.web import AppKey, StreamResponse, json_response
from yarl import URL

from src.exceptions import JSRError
from .mp4 import MP4Downloads


DOWNLOAD_ROUTES = {'download_video', 'download_subtitles', 'download_mp4', 'prepare_mp4'}
DOWNLOAD_PREFIX = '/api/rezka/downloads/'
_TTL = 600
_CHUNK_SIZE = 256 * 1024
_RANGE = re.compile(r'bytes=(?:[0-9]{1,20}-[0-9]{0,20}|-[0-9]{1,20})')
_SUBTITLE_TYPES = {'text/vtt', 'application/x-subrip', 'text/srt', 'text/plain'}
_PLAIN_TYPES = {'application/octet-stream', 'binary/octet-stream'}


class NoPublicCDNAddress(OSError):
  pass


class PublicResolver(AbstractResolver):
  def __init__(self):
    self.resolver = ThreadedResolver()

  async def resolve(self, host, port=0, family=0):
    addresses = await self.resolver.resolve(host, port, family)
    public = [record for record in addresses if ip_address(record['host']).is_global
              and not ip_address(record['host']).is_multicast]
    if not public:
      raise NoPublicCDNAddress('No public CDN address')
    return public

  async def close(self):
    await self.resolver.close()


@dataclass(frozen=True)
class Download:
  video: tuple[tuple[str, int], ...]
  subtitles: tuple[tuple[str, int], ...]
  filename: str
  deadline: float


class DownloadService:
  def __init__(self, client):
    self.client = client
    self.tickets = {}
    self.mp4 = MP4Downloads(self)

  @staticmethod
  def allowed_url(url):
    try:
      url = URL(url, encoded=True)
      host = url.raw_host
      if (url.scheme != 'https' or not host or url.port != 443
          or url.raw_user is not None or url.raw_password is not None
          or '%' in host or not re.fullmatch(r'[a-zA-Z0-9.-]+', host)):
        return None
      try:
        ip_address(host)
      except ValueError:
        return url.with_fragment(None)
    except (ValueError, UnicodeError):
      return None
    return None

  @asynccontextmanager
  async def open(self, url, byte_range):
    headers = {'Accept-Encoding': 'identity'}
    if byte_range:
      headers['Range'] = byte_range
    for _ in range(5):
      url = self.allowed_url(url)
      if url is None:
        raise JSRError('upstream_error', message='Invalid CDN URL')
      async with self.client.get(url, headers=headers, allow_redirects=False) as upstream:
        if upstream.status not in {301, 302, 303, 307, 308}:
          yield upstream
          return
        location = upstream.headers.get('Location')
        if not location:
          break
        url = url.join(URL(location, encoded=True))
    raise JSRError('upstream_error', message='Invalid CDN redirect')

  @staticmethod
  def resource_type(upstream, url, video):
    encoding = upstream.headers.get('Content-Encoding', 'identity').lower()
    if encoding != 'identity':
      return None
    content_type = upstream.content_type
    if video:
      if content_type == 'video/mp4' or (content_type in _PLAIN_TYPES and url.path.lower().endswith('.mp4')):
        return 'video/mp4'
      return None
    if content_type in _SUBTITLE_TYPES | _PLAIN_TYPES:
      path = url.path.lower()
      if content_type == 'text/vtt' or path.endswith('.vtt'):
        return 'text/vtt'
      if content_type in {'application/x-subrip', 'text/srt'} or path.endswith('.srt'):
        return 'application/x-subrip'
      if content_type == 'text/plain':
        return 'text/plain'
    return None

  @asynccontextmanager
  async def open_resource(self, candidates, byte_range, video):
    blocked_dns = False
    for url, expires_at in candidates:
      if expires_at <= time():
        continue
      accepted = False
      try:
        async with self.open(url, byte_range) as upstream:
          if self.usable(upstream, upstream.url, video) or (byte_range and upstream.status == 416):
            accepted = True
            yield upstream
            return
      except (JSRError, ClientError, TimeoutError, OSError, ValueError) as error:
        if accepted:
          raise
        blocked_dns |= isinstance(getattr(error, 'os_error', error), NoPublicCDNAddress)
    resource = 'Video CDN' if video else 'Subtitle CDN'
    if blocked_dns:
      raise JSRError('upstream_error', message=f'{resource} DNS returned only non-public addresses')
    raise JSRError('upstream_error', message=f'{resource} could not serve the download')

  def usable(self, upstream, url, video):
    return (upstream.status in {200, 206}
            and (upstream.status != 206 or upstream.headers.get('Content-Range'))
            and self.resource_type(upstream, url, video))

  def issue(self, video_source, subtitle_source, title, release=None):
    def candidates(source):
      if source is None:
        return ()
      return ((source.url, source.expires_at),) + (
        ((source.reserve, source.reserve_expires_at),) if source.reserve else ()
      )

    video = candidates(video_source)
    subtitles = candidates(subtitle_source)
    expires_at = min(int(time()) + _TTL, max(expiry for _, expiry in video))
    if subtitles:
      expires_at = min(expires_at, max(expiry for _, expiry in subtitles))
    lifetime = expires_at - time()
    if lifetime <= 0:
      raise JSRError('source_expired')

    season, episode = video_source.season, video_source.episode
    quality = re.sub(r'[^a-zA-Z0-9 _.-]', '_', video_source.title)[:40]
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', '_', title).strip(' .')[:100] or 'video'
    title = re.sub(r'\s+', '_', title)
    quality = re.sub(r'\s+', '.', quality)
    if season is not None:
      suffix = f'.S{season:02d}E{episode:02d}'
    elif release is not None:
      suffix = f'.{datetime.fromtimestamp(release, timezone.utc).year:04d}'
    else:
      suffix = ''
    filename = f'{title}{suffix}.{quality}.mp4'
    now = monotonic()
    for token, download in tuple(self.tickets.items()):
      if download.deadline <= now:
        del self.tickets[token]
    token = token_urlsafe(32)
    self.tickets[token] = Download(video, subtitles, filename, now + lifetime)
    base = DOWNLOAD_PREFIX + token
    return {
      'video_url': base + '/video',
      'subtitles_url': base + '/subtitles' if subtitles else None,
      'mp4_url': base + '/mp4' if subtitles else None,
      'prepare_url': base + '/prepare' if subtitles else None,
      'filename': filename,
      'expires_at': expires_at,
    }

  def get_ticket(self, req):
    token = req.match_info['ticket']
    download = self.tickets.get(token)
    if download is None:
      raise JSRError('not_found', message='Download ticket not found')
    if download.deadline <= monotonic():
      self.tickets.pop(token, None)
      raise JSRError('download_expired')
    return download

  async def prepare_merged(self, req):
    download = self.get_ticket(req)
    if not download.subtitles:
      raise JSRError('not_found', message='No subtitle track for this download')
    file_url = DOWNLOAD_PREFIX + req.match_info['ticket'] + '/mp4'
    return await self.mp4.prepare(req, download, file_url)

  async def transfer(self, req, video):
    download = self.get_ticket(req)
    candidates = download.video if video else download.subtitles
    if not candidates:
      raise JSRError('not_found', message='No subtitle track for this download')

    byte_range = req.headers.get('Range')
    if byte_range is not None and not _RANGE.fullmatch(byte_range):
      raise JSRError('invalid_range')

    response = None
    try:
      async with self.open_resource(candidates, byte_range, video) as upstream:
        if upstream.status == 416 and byte_range:
          headers = {'Cache-Control': 'no-store'}
          if content_range := upstream.headers.get('Content-Range'):
            headers['Content-Range'] = content_range
          error = JSRError('invalid_range', message='Requested range is not satisfiable')
          return json_response(**error.json, headers=headers)
        content_type = self.resource_type(upstream, upstream.url, video)
        headers = {
          'Content-Type': content_type,
          'Cache-Control': 'no-store',
          'Referrer-Policy': 'no-referrer',
          'X-Accel-Buffering': 'no',
          'X-Content-Type-Options': 'nosniff',
        }
        for key in ('Content-Length', 'Content-Range', 'Accept-Ranges'):
          if key in upstream.headers:
            headers[key] = upstream.headers[key]
        if video:
          filename, fallback = download.filename, 'video.mp4'
        else:
          extension = 'vtt' if content_type == 'text/vtt' else 'srt'
          fallback = f'subtitles.{extension}'
          filename = download.filename.removesuffix('.mp4') + '.' + extension
        encoded_name = quote(filename, safe='')
        headers['Content-Disposition'] = f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded_name}"
        response = StreamResponse(status=upstream.status, headers=headers)
        await response.prepare(req)
        async for chunk in upstream.content.iter_chunked(_CHUNK_SIZE):
          await response.write(chunk)
        await response.write_eof()
        return response
    except (ClientError, TimeoutError, OSError, ValueError):
      if response is None:
        raise JSRError('upstream_error', message='CDN connection failed') from None
      if req.transport is not None:
        req.transport.abort()
      return response


DOWNLOADS = AppKey('downloads', DownloadService)


async def download_ctx(app):
  resolver = PublicResolver()
  try:
    async with ClientSession(
      connector=TCPConnector(resolver=resolver),
      timeout=ClientTimeout(total=None, connect=10, sock_read=20),
      auto_decompress=False,
      cookie_jar=DummyCookieJar(),
    ) as client:
      service = DownloadService(client)
      app[DOWNLOADS] = service
      try:
        yield
      finally:
        await service.mp4.close()
  finally:
    await resolver.close()
