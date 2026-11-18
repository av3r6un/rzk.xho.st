from sqlalchemy import select, update
from src.models import ActiveEncoder
from contextlib import suppress
from aiohttp.web import AppKey
from time import time
import logging
import asyncio
import ffmpeg
import os
import re

DEFAULT_ENCODERS = 'libx264,libx265,libsvtav1,hevc_nvenc'
ENCODER_NAME = re.compile(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,63}')
VIDEO_ENCODER = re.compile(r'^\s*V[.A-Z]{5}\s+(\S+)\s+', re.MULTILINE)
PROBE_OPTIONS = {
  'libx264': {'preset': 'fast', 'crf': 25},
  'libx265': {'preset': 'medium', 'crf': 24},
  'libsvtav1': {'preset': 9, 'crf': 32},
  'hevc_nvenc': {'preset': 'p5', 'cq': 28},
}

logger = logging.getLogger(__name__)


class EncoderChecks:
  def __init__(self, session_factory):
    self.session_factory = session_factory
    self.binary = os.getenv('RZK_FFMPEG', 'ffmpeg')
    self.registration_lock = asyncio.Lock()
    self.task = None
    self.repeat = False

  async def register(self, names):
    async with self.registration_lock, self.session_factory.begin() as session:
      existing = set(await session.scalars(select(ActiveEncoder.name)))
      new = set(names) - existing
      session.add_all(ActiveEncoder(name=name) for name in sorted(new))
      return bool(new)

  def refresh(self, *, added=False):
    if self.task is None or self.task.done():
      self.task = asyncio.create_task(self.run())
    elif added:
      self.repeat = True

  async def run(self):
    try:
      configured = os.getenv('RZK_FFMPEG_ENCODERS', DEFAULT_ENCODERS)
      names = (item.strip() for item in configured.split(','))
      await self.register(name for name in names if ENCODER_NAME.fullmatch(name))
      while True:
        self.repeat = False
        await self.check_all()
        if not self.repeat:
          break
    except Exception:
      logger.exception('FFmpeg encoder refresh failed')

  async def check_all(self):
    async with self.session_factory() as session:
      names = (await session.scalars(select(ActiveEncoder.name).order_by(ActiveEncoder.name))).all()
    if not names:
      return

    listed = None
    listing_error = None
    try:
      code, output, error = await run_ffmpeg([self.binary, '-hide_banner', '-encoders'])
      if code:
        listing_error = error or f'FFmpeg exited with code {code}'
      else:
        listed = set(VIDEO_ENCODER.findall(output))
    except FileNotFoundError:
      listed = set()
      listing_error = 'FFmpeg executable not found'
    except (OSError, TimeoutError) as exc:
      listing_error = str(exc) or 'FFmpeg encoder listing timed out'

    for name in names:
      available = None if listed is None else name in listed
      error = listing_error
      if available:
        error = await self.probe(name)
      elif not error:
        error = 'Video encoder is absent from this FFmpeg build'

      async with self.registration_lock, self.session_factory.begin() as session:
        await session.execute(
          update(ActiveEncoder).where(ActiveEncoder.name == name).values(
            available=available, working=available is True and error is None,
            checked_at=int(time()), error=error[:512] if error else None,
          )
        )

  async def probe(self, name):
    graph = (
      ffmpeg.input('testsrc2=size=320x180:rate=25', f='lavfi')
      .output('-', f='null', vcodec=name, vframes=8, an=None, **PROBE_OPTIONS.get(name, {}))
      .global_args('-nostdin', '-hide_banner', '-loglevel', 'error', '-abort_on', 'empty_output')
    )
    try:
      code, _, error = await run_ffmpeg(graph.compile(cmd=self.binary))
    except TimeoutError:
      return 'FFmpeg encoder probe timed out'
    except OSError as exc:
      return str(exc)
    if code:
      return error or f'FFmpeg exited with code {code}'
    return None


async def run_ffmpeg(args):
  process = await asyncio.create_subprocess_exec(
    *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
  )
  try:
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
    error = stderr.decode(errors='replace').strip()
    return process.returncode, stdout.decode(errors='replace'), error
  finally:
    if process.returncode is None:
      with suppress(ProcessLookupError):
        process.kill()
      await process.communicate()


ENCODER_CHECKS = AppKey('ffmpeg_encoder_checks', EncoderChecks)


async def encoder_checks_ctx(app):
  checks = app[ENCODER_CHECKS] = EncoderChecks(app['db_sessionmaker'])
  checks.refresh()
  yield
  if checks.task is not None:
    checks.task.cancel()
    with suppress(asyncio.CancelledError):
      await checks.task
