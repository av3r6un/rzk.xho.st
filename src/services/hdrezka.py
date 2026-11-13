from base64 import b64decode, b64encode
from binascii import Error
from datetime import datetime, timezone
from hashlib import sha256
from itertools import product
import re
from time import time_ns
from urllib.parse import unquote, urljoin, urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, DummyCookieJar
from bs4 import BeautifulSoup

from src.exceptions import JSRError


ORIGIN = 'https://rezka.fi'
_MEDIA_HOSTS = {urlsplit(ORIGIN).netloc, 'hdrezka.ag'}
_MEDIA_PATH = re.compile(r'/(films|series|cartoons|animation)/[a-z0-9_-]+/([1-9][0-9]{0,8})-[a-z0-9_-]+\.html')
_TRASH = tuple(
  b64encode(''.join(chars).encode()).decode()
  for length in (2, 3)
  for chars in product('@#!^$', repeat=length)
)
_LINK_GROUP = re.compile(r'\[([^\]]+)\]([^,]+)')


def parse_media_url(value):
  if not isinstance(value, str) or len(value) > 1024:
    raise JSRError('invalid_payload')
  try:
    url = urlsplit(value)
  except ValueError:
    raise JSRError('invalid_payload') from None
  match = _MEDIA_PATH.fullmatch(url.path)
  if url.scheme != 'https' or url.netloc.lower() not in _MEDIA_HOSTS or not match:
    raise JSRError('invalid_payload', message='Expected an HTTPS media URL on rezka.fi or hdrezka.ag')
  return url.path, int(match[2]), match[1]


def _web_url(value):
  try:
    url = urlsplit(value)
    return url.scheme in ('http', 'https') and url.hostname and not url.username
  except ValueError:
    return False


def _option_id(label):
  normalized = ' '.join(label.casefold().split())
  if re.fullmatch(r'[a-z0-9][a-z0-9 _-]{0,63}', normalized):
    return normalized.replace(' ', '-')
  return sha256(normalized.encode()).hexdigest()[:24]


def group_download_streams(streams):
  groups = {}
  for stream in streams:
    link = stream['url']
    if unquote(urlsplit(link).path).lower().endswith(('.m3u8', '.mpd')):
      continue
    group = groups.setdefault(stream['quality_id'], {
      'id': str(len(groups) + 1),
      'title': stream['quality'],
      'url': link,
      'reserve': None,
    })
    if link != group['url'] and group['reserve'] is None:
      group['reserve'] = link
  return groups


def parse_streams(payload):
  if not isinstance(payload, dict) or not payload.get('success'):
    raise JSRError('upstream_error', message='HDRezka did not return a stream')
  raw_streams = payload.get('url')
  if not isinstance(raw_streams, str):
    raise JSRError('upstream_error')
  try:
    stream_list = raw_streams.strip()
    if not stream_list.startswith('['):
      encoded = stream_list.removeprefix('#h').replace('//_//', '')
      for token in _TRASH:
        encoded = encoded.replace(token, '')
      stream_list = b64decode(encoded + '==').decode()
  except (Error, UnicodeError, ValueError):
    raise JSRError('upstream_error') from None
  streams = [
    {'quality': label, 'quality_id': _option_id(label), 'url': link}
    for quality, links in _LINK_GROUP.findall(stream_list)
    if (label := BeautifulSoup(quality, 'html.parser').get_text(' ', strip=True))
    for link in map(str.strip, links.split(' or '))
    if _web_url(link)
  ]
  if not streams:
    raise JSRError('upstream_error')
  raw_subtitles = payload.get('subtitle')
  subtitles = [
    {'language': language.strip(), 'language_id': _option_id(language), 'url': link}
    for language, links in _LINK_GROUP.findall(raw_subtitles)
    for link in map(str.strip, links.split(' or '))
    if _web_url(link)
  ] if isinstance(raw_subtitles, str) else []
  return {'streams': streams, 'subtitles': subtitles}


async def get_streams(media, cookies, translator_id, season, episode):
  if not cookies:
    raise JSRError('bad_request', message='Configure HDRezka cookies first')
  data = {'id': str(media.id), 'translator_id': str(translator_id)}
  if season is None:
    data['action'] = 'get_movie'
  else:
    data.update(action='get_stream', season=str(season), episode=str(episode))

  headers = {
    'Cookie': cookies,
    'Origin': ORIGIN,
    'Referer': ORIGIN + media.path,
    'X-Requested-With': 'XMLHttpRequest',
  }
  try:
    async with ClientSession(timeout=ClientTimeout(total=20), cookie_jar=DummyCookieJar()) as client:
      async with client.post(
        ORIGIN + '/ajax/get_cdn_series/',
        params={'t': str(time_ns() // 1_000_000)},
        data=data,
        headers=headers,
        allow_redirects=False,
      ) as response:
        if response.status != 200:
          raise JSRError('upstream_error')
        payload = await response.json(content_type=None)
  except (ClientError, TimeoutError, ValueError):
    raise JSRError('upstream_error') from None
  return parse_streams(payload)


_MONTHS = (
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
)


def _release_timestamp(value):
  match = re.fullmatch(r'(\d{1,2})\s+([а-я]+)\s+(\d{4})(?:\s+года)?', value.casefold())
  if not match:
    return None
  day, month, year = match.groups()
  try:
    date = datetime(int(year), _MONTHS.index(month) + 1, int(day), tzinfo=timezone.utc)
  except ValueError:
    return None
  return int(date.timestamp())


def _parse_seasons(soup):
  seasons = {}
  episodes = {}
  for item in soup.select('.b-simple_season__item'):
    season_id = item.get('data-tab_id', '')
    if re.fullmatch(r'[1-9][0-9]{0,4}', season_id):
      seasons[int(season_id)] = item.get_text(' ', strip=True)

  for item in soup.select('.b-simple_episode__item'):
    season_id = item.get('data-season_id', '')
    episode_id = item.get('data-episode_id', '')
    if not all(re.fullmatch(r'[1-9][0-9]{0,4}', value) for value in (season_id, episode_id)):
      continue
    season_id, episode_id = int(season_id), int(episode_id)
    seasons.setdefault(season_id, '')
    episodes.setdefault(season_id, {})[episode_id] = item.get_text(' ', strip=True)

  return [
    {
      'id': season_id,
      'title': title or f'{season_id} сезон',
      'episodes': [
        {'id': episode_id, 'title': label or f'{episode_id} серия'}
        for episode_id, label in sorted(episodes.get(season_id, {}).items())
      ],
    }
    for season_id, title in sorted(seasons.items())
  ]


def _parse_external_ids(main):
  ids = {}
  for link in main.select('.b-post__info_rates a[href]'):
    href = link['href']
    try:
      if href.startswith('/help/'):
        token = href.removeprefix('/help/').removesuffix('/')
        href = unquote(b64decode(token, validate=True).decode('utf-8'))
      url = urlsplit(href)
    except (Error, UnicodeError, ValueError):
      continue
    if url.scheme not in ('http', 'https'):
      continue
    if url.netloc.lower() in ('imdb.com', 'www.imdb.com'):
      match = re.fullmatch(r'/title/(tt[0-9]+)/?', url.path)
      if match:
        ids.setdefault('imdb_id', match[1])
    elif url.netloc.lower() in ('kinopoisk.ru', 'www.kinopoisk.ru'):
      match = re.fullmatch(r'/(?:film|series)/([1-9][0-9]*)/?', url.path)
      if match:
        ids.setdefault('kp_id', match[1])
  return ids


def _parse_media_page(html, url):
  soup = BeautifulSoup(html, 'html.parser')
  main = soup.select_one('.b-content__main')
  title = main.select_one('.b-post__title h1') if main else None
  if not title or not title.get_text(strip=True):
    raise JSRError('upstream_error')

  original_title = main.select_one('.b-post__origtitle')
  description = main.select_one('.b-post__description_text') or main.select_one('[itemprop="description"]')
  image = main.select_one('.b-post__infotable_left .b-sidecover img[itemprop="image"]')
  image_url = image.get('src') if image else None
  info = {}
  for row in main.select('table.b-post__info tr'):
    cells = row.find_all('td', recursive=False)
    if len(cells) >= 2:
      label = cells[0].get_text(strip=True).rstrip(':').strip().casefold()
      info[label] = ' '.join(cells[1].get_text().split())

  translators = {}
  for item in soup.select('.b-translator__item'):
    translator = item.get('data-translator_id') or ''
    if re.fullmatch(r'[1-9][0-9]{0,8}', translator):
      translators[int(translator)] = item.get('title')

  genres = info.get('жанр') or info.get('жанры', '')
  return {
    'url': url,
    'name': title.get_text(strip=True),
    'original_name': original_title.get_text(strip=True) if original_title else None,
    'cover': urljoin(url, image_url) if image_url else None,
    'slogan': info.get('слоган') or None,
    'description': ' '.join(description.get_text().split()) if description else '',
    'release': _release_timestamp(info.get('дата выхода', '')),
    'country': info.get('страна') or None,
    'genres': [genre.strip() for genre in genres.split(',') if genre.strip()],
    'translators': [{'id': uid, 'title': title} for uid, title in translators.items()],
    'seasons': _parse_seasons(soup),
    'external_ids': _parse_external_ids(main),
  }


async def get_media_details(media, cookies):
  url = ORIGIN + media.path
  headers = {'Cookie': cookies} if cookies else {}
  try:
    async with ClientSession(timeout=ClientTimeout(total=20), cookie_jar=DummyCookieJar()) as client:
      async with client.get(
        url, headers=headers, allow_redirects=False,
      ) as response:
        if response.status != 200:
          raise JSRError('upstream_error')
        details = _parse_media_page(await response.text(), url)
  except (ClientError, TimeoutError, ValueError):
    raise JSRError('upstream_error') from None
  return details
