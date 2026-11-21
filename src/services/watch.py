import asyncio
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import json
import logging
from math import ceil
import os
from pathlib import Path
import re
from secrets import token_urlsafe
from time import time
from urllib.parse import unquote, urlsplit

from aiohttp import ClientConnectorDNSError, ClientError
from aiohttp.web import AppKey, Response, StreamResponse
from yarl import URL

from src.exceptions import JSRError
from .download_sources import source_expiry
from .downloads import DOWNLOADS, SINGLE_BYTE_RANGE, NoPublicCDNAddress
from .hdrezka import group_download_streams


WATCH_PREFIX = '/api/watch/session/'
WATCH_ROUTES = {'watch_master', 'watch_asset'}
_TTL = 4 * 60 * 60
_TEXT_LIMIT = 2 * 1024 * 1024
_PROBE_LIMIT = 1024 * 1024
_MAX_WATCH_HEIGHT = 1080
_PREMIUM_QUALITY = re.compile(r'ultra|ультра|\b(?:uhd|(?:[2-9]|[1-9][0-9]+)\s*k)(?![a-z])', re.IGNORECASE)
_QUALITY_HEIGHT = re.compile(r'(?<![0-9])([0-9]{3,4})(?:\s*[pр]|\s*$)', re.IGNORECASE)
_MEDIA_TAGS = {
  '#EXT-X-VERSION', '#EXT-X-TARGETDURATION', '#EXT-X-MEDIA-SEQUENCE',
  '#EXT-X-DISCONTINUITY-SEQUENCE', '#EXT-X-DISCONTINUITY', '#EXT-X-BYTERANGE',
  '#EXT-X-ENDLIST', '#EXT-X-INDEPENDENT-SEGMENTS', '#EXT-X-PROGRAM-DATE-TIME',
  '#EXT-X-GAP', '#EXT-X-START', '#EXTINF',
}
_URI = re.compile(r'(?<=[,:])URI="([^"\r\n]+)"')
_MAP = re.compile(r'^X-TIMESTAMP-MAP[ \t]*=', re.MULTILINE)
_VTT = re.compile(r'^WEBVTT(?:[ \t][^\n]*)?\n')
_LANGUAGES = {
  'русский': 'ru', 'русские': 'ru', 'russian': 'ru',
  'английский': 'en', 'английские': 'en', 'english': 'en',
  'украинский': 'uk', 'українська': 'uk', 'ukrainian': 'uk',
  'испанский': 'es', 'spanish': 'es', 'французский': 'fr', 'french': 'fr',
  'немецкий': 'de', 'german': 'de', 'японский': 'ja', 'japanese': 'ja',
}
_TYPES = {
  '.ts': 'video/mp2t', '.mp4': 'video/mp4', '.m4s': 'video/iso.segment',
  '.m4a': 'audio/mp4', '.aac': 'audio/aac', '.mp3': 'audio/mpeg',
  '.ac3': 'audio/ac3', '.ec3': 'audio/ec3',
}
_HEADERS = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
            'X-Content-Type-Options': 'nosniff'}


def upstream_error(message):
  return JSRError('upstream_error', message=message)


def watch_height(label):
  height = _QUALITY_HEIGHT.search(label)
  return int(height[1]) if height else 0


def supported_watch_quality(label):
  if _PREMIUM_QUALITY.search(label):
    return False
  return watch_height(label) <= _MAX_WATCH_HEIGHT


def watch_debug_enabled():
  return os.getenv('DEBUG', '').strip().lower() in {'1', 'true', 'yes', 'on'}


def save_dev_manifest(master):
  if not watch_debug_enabled():
    return
  cache = Path(__file__).resolve().parents[2] / 'cache'
  pending = cache / f'.master-{token_urlsafe(8)}.tmp'
  try:
    cache.mkdir(exist_ok=True)
    pending.write_text(master, encoding='utf-8', newline='\n')
    pending.replace(cache / 'master.m3u8')
  except OSError:
    logging.warning('Could not save AirPlay manifest in the dev cache', exc_info=True)
    with suppress(OSError):
      pending.unlink(missing_ok=True)


def dns_failure(error):
  cause = error.os_error
  if isinstance(cause, NoPublicCDNAddress):
    return f'CDN DNS returned no public IP addresses for {error.host}'
  code = f' (resolver code {cause.errno})' if cause.errno is not None else ''
  return f'CDN DNS lookup failed for {error.host}{code}'


def playlist_response(text):
  response = Response(text=text, content_type='application/vnd.apple.mpegurl', headers=_HEADERS)
  response.enable_compression()
  return response


def subtitle_playlist(duration):
  return '\n'.join((
    '#EXTM3U', '#EXT-X-VERSION:3', f'#EXT-X-TARGETDURATION:{ceil(duration)}',
    '#EXT-X-PLAYLIST-TYPE:VOD', f'#EXTINF:{duration:f},', 'full.vtt', '#EXT-X-ENDLIST', '',
  ))


def subtitle_text(raw, ticks):
  text = raw.replace('\r\n', '\n').replace('\r', '\n')
  header = _VTT.match(text)
  if not header:
    raise upstream_error('CDN returned invalid WebVTT')
  if _MAP.search(text.split('\n\n', 1)[0]):
    return text
  if ticks is None:
    raise upstream_error('Could not synchronize WebVTT with the video')
  return text[:header.end()] + f'X-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:{ticks}\n' + text[header.end():]


@dataclass
class WatchSession:
  expires_at: int
  master: str = ''
  playlists: dict[str, str] = field(default_factory=dict)
  media: dict[str, tuple[URL, str]] = field(default_factory=dict)
  subtitles: dict[str, str] = field(default_factory=dict)
  files: dict[str, tuple[tuple[tuple[str, int], ...], bool]] = field(default_factory=dict)


@dataclass
class VideoPlaylist:
  text: str
  duration: Decimal
  first_segment: URL
  first_duration: Decimal
  byte_range: str | None
  init: URL | None
  init_range: str | None


def relative_resource(cdn, base, reference):
  target = cdn.allowed_url(base.join(URL(reference, encoded=True)))
  if target is None:
    raise upstream_error('Invalid HLS resource URL')
  return target


def first_byte_range(value):
  match = re.fullmatch(r'([0-9]{1,16})(?:@([0-9]{1,16}))?', value)
  if not match or int(match[1]) == 0:
    raise upstream_error('Invalid HLS byte range')
  start = int(match[2] or 0)
  return f'bytes={start}-{start + int(match[1]) - 1}'


def rewrite_video(cdn, session, base, text):
  lines = [line.strip() for line in text.splitlines() if line.strip()]
  if not lines or lines[0] != '#EXTM3U':
    raise upstream_error('CDN response is not an HLS playlist')
  if any(line.startswith('#EXT-X-STREAM-INF:') for line in lines):
    raise upstream_error('CDN returned an HLS master playlist instead of a media playlist')
  if '#EXT-X-ENDLIST' not in lines:
    raise upstream_error('HLS media playlist is missing EXT-X-ENDLIST')

  output = ['#EXTM3U']
  duration = Decimal(0)
  segment_duration = None
  first_segment = first_duration = init = byte_range = init_range = None
  paths = {}
  for line in lines[1:]:
    tag, _, value = line.partition(':')
    if tag == '#EXTINF':
      segment_duration = Decimal(value.partition(',')[0])
      if not segment_duration.is_finite() or not 0 < segment_duration <= 86400:
        raise upstream_error('Invalid HLS segment duration')
    elif tag == '#EXT-X-BYTERANGE' and first_segment is None:
      byte_range = first_byte_range(value)

    if not line.startswith('#'):
      if segment_duration is None:
        raise upstream_error('Unexpected URI in HLS media playlist')
      url = relative_resource(cdn, base, line)
      if first_segment is None:
        first_segment, first_duration = url, segment_duration
      duration += segment_duration
      segment_duration = None
      suffix = '.' + unquote(url.path).rsplit('.', 1)[-1].lower()
      line = media_path(session, paths, url, _TYPES.get(suffix, 'application/octet-stream'))
    elif tag in {'#EXT-X-MAP', '#EXT-X-KEY'}:
      match = _URI.search(line)
      if match:
        url = relative_resource(cdn, base, match[1])
        content_type = 'video/mp4' if tag == '#EXT-X-MAP' else 'application/octet-stream'
        if tag == '#EXT-X-MAP' and first_segment is None:
          init = url
          match_range = re.search(r'(?:[:,])BYTERANGE="([^"]+)"', line)
          init_range = first_byte_range(match_range[1]) if match_range else None
        path = media_path(session, paths, url, content_type)
        line = line[:match.start(1)] + path + line[match.end(1):]
      elif tag == '#EXT-X-MAP' or value != 'METHOD=NONE':
        raise upstream_error('Invalid HLS initialization or key URI')
    elif tag in {'#EXT-X-DEFINE', '#EXT-X-STREAM-INF', '#EXT-X-MEDIA', '#EXT-X-I-FRAMES-ONLY'}:
      raise upstream_error('Unsupported HLS media playlist tag')
    elif tag not in _MEDIA_TAGS:
      continue
    output.append(line)

  if first_segment is None or segment_duration is not None:
    raise upstream_error('HLS media playlist has no complete video segments')
  output.insert(1, '#EXT-X-PLAYLIST-TYPE:VOD')
  session.media.update({path: resource for resource, path in paths.items()})
  return VideoPlaylist('\n'.join(output) + '\n', duration, first_segment, first_duration,
                       byte_range, init, init_range)


def media_path(session, paths, url, content_type):
  path = paths.setdefault((url, content_type), f'media/{len(session.media) + len(paths)}')
  return '../' + path


def stream_codec(stream):
  codec = stream.get('codec_name')
  if codec == 'h264':
    # ffprobe writes codec configuration bytes as a hex dump, including the SPS for MPEG-TS.
    dump = stream.get('extradata', '')
    try:
      data = bytes.fromhex(' '.join(line.partition(': ')[2].partition('  ')[0] for line in dump.splitlines()))
    except ValueError:
      return None
    if data[:1] == b'\x01' and len(data) >= 4:
      tag = 'avc3' if stream.get('codec_tag_string') == 'avc3' else 'avc1'
      return f'{tag}.{data[1:4].hex()}'
    for nal in data.split(b'\x00\x00\x01')[1:]:
      if len(nal) >= 4 and nal[0] & 31 == 7:
        return f'avc1.{nal[1:4].hex()}'
  elif codec == 'aac':
    object_type = {'Main': 1, 'LC': 2, 'SSR': 3, 'LTP': 4, 'HE-AAC': 5, 'HE-AACv2': 29}.get(stream.get('profile'))
    if object_type is not None:
      return f'mp4a.40.{object_type}'
  return {'ac3': 'ac-3', 'eac3': 'ec-3', 'mp3': 'mp4a.40.34'}.get(codec)


async def inspect_video(sample):
  try:
    process = await asyncio.create_subprocess_exec(
      os.getenv('RZK_FFPROBE', 'ffprobe'), '-v', 'error', '-protocol_whitelist', 'pipe',
      '-format_whitelist', 'mpegts,mov', '-show_data', '-show_entries',
      'stream=codec_type,codec_name,codec_tag_string,profile,extradata,width,height,start_time',
      '-of', 'json', 'pipe:0', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.DEVNULL,
    )
  except (OSError, NotImplementedError):
    return {}
  try:
    stdout, _ = await asyncio.wait_for(process.communicate(sample), timeout=5)
    if process.returncode == 0:
      streams = json.loads(stdout).get('streams', ())
      video = next((stream for stream in streams if stream.get('codec_type') == 'video'), {})
      if video:
        codecs = [stream_codec(stream) for stream in streams if stream.get('codec_type') in {'video', 'audio'}]
        if all(codecs):
          video['codecs'] = list(dict.fromkeys(codecs))
      return video
  except TimeoutError:
    pass
  finally:
    if process.returncode is None:
      with suppress(ProcessLookupError):
        process.kill()
      await process.communicate()
  return {}


class WatchService:
  def __init__(self, cdn):
    self.cdn = cdn
    self.sessions = {}

  def issue_files(self, sources):
    now = int(time())
    session = WatchSession(now + _TTL)
    streams = []
    subtitles = []
    candidates = {}
    available = [stream for stream in sources['streams'] if supported_watch_quality(stream['quality'])]
    for stream in available:
      url = stream['url']
      if self.cdn.allowed_url(url) is None:
        continue
      expiry = min(source_expiry(url, 'video') or session.expires_at, session.expires_at)
      if expiry > now:
        candidates[url] = expiry
    active = (stream for stream in available if stream['url'] in candidates)
    for quality_id, stream in group_download_streams(active).items():
      links = tuple((url, candidates[url]) for url in (stream['url'], stream['reserve']) if url)
      session.expires_at = min(session.expires_at, max(expiry for _, expiry in links))
      path = f'video/{len(streams)}.mp4'
      session.files[path] = (links, True)
      streams.append({'quality': stream['title'], 'quality_id': quality_id, 'url': path})
    if not streams:
      raise upstream_error('HDRezka returned no playable MP4 sources up to 1080p for this selection')

    languages = {}
    for track in sources['subtitles']:
      url = self.cdn.allowed_url(track['url'])
      if url is None or not url.path.lower().endswith('.vtt'):
        continue
      expiry = min(source_expiry(track['url'], 'subtitles') or session.expires_at, session.expires_at)
      if expiry > now:
        _, links = languages.setdefault(track['language_id'], (track['language'], {}))
        links[track['url']] = expiry
    for language_id, (language, links) in languages.items():
      path = f'subs/{len(subtitles)}.vtt'
      session.files[path] = (tuple(links.items()), False)
      subtitles.append({'language': language, 'language_id': language_id, 'url': path})

    ticket = self.store(session)
    for source in (*streams, *subtitles):
      source['url'] = f'{WATCH_PREFIX}{ticket}/{source["url"]}'
    return {'streams': streams, 'subtitles': subtitles, 'expires_at': session.expires_at}

  async def read_text(self, url):
    async with self.cdn.open(url, None, compressed=True) as upstream:
      if upstream.status != 200:
        raise upstream_error(f'CDN responded with HTTP {upstream.status} for an HLS playlist or subtitle track')
      body = bytearray()
      async for chunk in upstream.content.iter_chunked(64 * 1024):
        body.extend(chunk)
        if len(body) > _TEXT_LIMIT:
          raise upstream_error('HLS playlist or subtitle track is too large')
      return upstream.url, body.decode('utf-8-sig')

  async def sample(self, url, byte_range):
    original = byte_range or f'bytes=0-{_PROBE_LIMIT - 1}'
    start, end = map(int, original.removeprefix('bytes=').split('-'))
    requested = f'bytes={start}-{min(end, start + _PROBE_LIMIT - 1)}'
    limit = min(_PROBE_LIMIT, end - start + 1)
    async with self.cdn.open(url, requested) as upstream:
      if upstream.status not in {200, 206} or (start and upstream.status != 206):
        return b'', 0
      total = (upstream.headers.get('Content-Range') or '').rpartition('/')[2]
      size = end - start + 1 if byte_range else int(total) if total.isdecimal() else upstream.content_length
      sample = bytearray()
      while len(sample) < limit:
        chunk = await upstream.content.read(limit - len(sample))
        if not chunk:
          break
        sample.extend(chunk)
      return sample, size or len(sample)

  async def variant(self, session, candidates, failures):
    for url, expiry in candidates:
      try:
        base, source = await self.read_text(url)
        playlist = rewrite_video(self.cdn, session, base, source)
      except JSRError as error:
        failures[str(error)] += 1
        continue
      except (ValueError, InvalidOperation):
        failures['Malformed HLS playlist or resource URI'] += 1
        continue
      except ClientConnectorDNSError as error:
        failures[dns_failure(error)] += 1
        continue
      except (ClientError, TimeoutError, OSError) as error:
        failures[f'CDN connection failed ({type(error).__name__})'] += 1
        continue
      return await self.describe_variant(playlist, expiry)
    return None

  async def describe_variant(self, playlist, expiry):
    details, size = {}, 0
    try:
      segment, size = await self.sample(playlist.first_segment, playlist.byte_range)
      init, _ = await self.sample(playlist.init, playlist.init_range) if playlist.init else (b'', 0)
      if segment and (init or playlist.init is None):
        details = await inspect_video(init + segment)
    except (JSRError, ClientError, TimeoutError, OSError, ValueError):
      pass
    return playlist, expiry, details, size

  async def issue(self, sources):
    now = int(time())
    session = WatchSession(now + _TTL)
    groups = {}
    failures = Counter()
    for stream in sources['streams']:
      if not supported_watch_quality(stream['quality']):
        continue
      raw_url = stream['url']
      try:
        path = URL(raw_url, encoded=True).raw_path
      except ValueError:
        failures['Malformed source URL'] += 1
        continue
      if not unquote(path).lower().endswith('.m3u8'):
        continue
      url = self.cdn.allowed_url(raw_url)
      if url is None:
        failures['HLS source URL failed HTTPS validation'] += 1
        continue
      expiry = source_expiry(raw_url, 'video') or session.expires_at
      if expiry <= now:
        failures['HLS source URL expired'] += 1
        continue
      groups.setdefault(stream['quality_id'], (stream['quality'], {}))[1][url] = expiry

    if not groups and not failures:
      raise upstream_error('HDRezka returned no .m3u8 source URLs up to 1080p for this selection')
    ranked = sorted(groups.values(), key=lambda group: watch_height(group[0]), reverse=True)
    for label, candidates in ranked:
      variant = await self.variant(session, candidates.items(), failures)
      if variant is not None:
        break
    else:
      reasons = '; '.join(f'{reason} ({count})' for reason, count in failures.most_common(3))
      raise upstream_error(f'No playable HLS media playlist: {reasons}')

    playlist, expiry, details, size = variant
    path = 'video/0.m3u8'
    session.playlists[path] = playlist.text
    session.expires_at = min(session.expires_at, expiry)
    height = details.get('height') or watch_height(label) or 720
    bandwidth = max(ceil(Decimal(size) * 10 / playlist.first_duration), height * 3000)
    attrs = f'BANDWIDTH={bandwidth}'
    if details.get('width') and details.get('height'):
      attrs += f',RESOLUTION={details["width"]}x{details["height"]}'
    lines = ['#EXTM3U', '#EXT-X-VERSION:7']
    await self.add_subtitles(session, sources['subtitles'], playlist.duration, details.get('start_time'), lines)
    if session.subtitles:
      attrs += ',SUBTITLES="subs"'
    if codecs := details.get('codecs'):
      codecs = ','.join([*codecs, 'wvtt'] if session.subtitles else codecs)
      attrs += f',CODECS="{codecs}"'
    lines.extend((f'#EXT-X-STREAM-INF:{attrs}', path))
    session.master = '\n'.join(lines) + '\n'
    ticket = self.store(session)
    save_dev_manifest(session.master)
    return {
      'url': f'{WATCH_PREFIX}{ticket}/master.m3u8',
      'expires_at': session.expires_at,
      'subtitle_count': len(session.subtitles),
    }

  async def add_subtitles(self, session, tracks, duration, start_time, lines):
    ticks = None
    with suppress(InvalidOperation):
      start = Decimal(start_time if start_time is not None else 'NaN')
      if start.is_finite():
        ticks = round(start * 90000) % (1 << 33)
    groups = {}
    for track in tracks:
      url = track['url']
      if unquote(urlsplit(url).path).lower().endswith('.vtt'):
        groups.setdefault(track['language'], []).append(url)
    for index, (label, urls) in enumerate(groups.items()):
      name = re.sub(r'["\x00-\x1f\x7f]', '', label).strip() or f'Subtitles {index + 1}'
      last_error = 'CDN connection failed'
      for url in urls:
        if self.cdn.allowed_url(url) is None:
          last_error = 'CDN URL failed HTTPS validation'
          continue
        try:
          _, raw = await self.read_text(url)
          text = subtitle_text(raw, ticks)
        except JSRError as error:
          last_error = str(error)
          continue
        except (ClientError, TimeoutError, OSError, ValueError) as error:
          last_error = type(error).__name__
          continue
        break
      else:
        raise upstream_error(f'Could not prepare HLS subtitles ({name}): {last_error}')
      path = f'subs/{index}'
      session.playlists[f'{path}/index.m3u8'] = subtitle_playlist(duration)
      session.subtitles[f'{path}/full.vtt'] = text
      normalized = name.casefold()
      language = _LANGUAGES.get(normalized, normalized if re.fullmatch(r'[a-z]{2,3}(?:-[a-z]{2,8})?', normalized) else 'und')
      default = 'YES' if index == 0 else 'NO'
      lines.append(f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="{name}",'
                   f'LANGUAGE="{language}",DEFAULT={default},AUTOSELECT=YES,URI="{path}/index.m3u8"')

  def store(self, session):
    now = time()
    if session.expires_at <= now:
      raise JSRError('source_expired')
    self.sessions = {ticket: active for ticket, active in self.sessions.items() if active.expires_at > now}
    ticket = token_urlsafe(32)
    self.sessions[ticket] = session
    return ticket

  def get(self, ticket):
    session = self.sessions.get(ticket)
    if session is None:
      raise JSRError('not_found', message='Watch session not found')
    if session.expires_at <= time():
      self.sessions.pop(ticket, None)
      raise JSRError('watch_expired')
    return session

  async def transfer(self, req, url, content_type):
    byte_range = req.headers.get('Range')
    if byte_range is not None and not SINGLE_BYTE_RANGE.fullmatch(byte_range):
      raise JSRError('invalid_range')
    response = None
    try:
      async with self.cdn.open(url, byte_range) as upstream:
        headers = {**_HEADERS, 'X-Accel-Buffering': 'no'}
        if upstream.status == 416 and byte_range:
          if content_range := upstream.headers.get('Content-Range'):
            headers['Content-Range'] = content_range
          return Response(status=416, headers=headers)
        if (upstream.status not in {200, 206}
            or (upstream.status == 206 and not upstream.headers.get('Content-Range'))
            or upstream.headers.get('Content-Encoding', 'identity').lower() != 'identity'):
          raise upstream_error('CDN could not serve the HLS segment')
        headers['Content-Type'] = content_type
        for key in ('Content-Length', 'Content-Range', 'Accept-Ranges'):
          if key in upstream.headers:
            headers[key] = upstream.headers[key]
        response = StreamResponse(status=upstream.status, headers=headers)
        await response.prepare(req)
        if req.method != 'HEAD':
          async for chunk in upstream.content.iter_chunked(256 * 1024):
            await response.write(chunk)
        await response.write_eof()
        return response
    except (ClientError, TimeoutError, OSError, ValueError) as error:
      if response is None:
        if isinstance(error, ClientConnectorDNSError):
          raise upstream_error(dns_failure(error)) from None
        raise upstream_error('CDN connection failed') from None
      if req.transport is not None:
        req.transport.abort()
      return response


WATCH = AppKey('watch', WatchService)


async def watch_ctx(app):
  app[WATCH] = WatchService(app[DOWNLOADS])
  yield
