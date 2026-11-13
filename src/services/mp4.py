import asyncio
from contextlib import suppress
from dataclasses import dataclass
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.parse import quote

from aiohttp import ClientError
from aiohttp.web import StreamResponse, WebSocketResponse

from src.exceptions import JSRError


_CHUNK_SIZE = 256 * 1024
_MAX_SUBTITLE_BYTES = 8 * 1024 * 1024


async def copy_source(service, candidates, destination, *, video, progress=None):
  size = 0
  async with service.open_resource(candidates, None, video) as source:
    if source.status != 200:
      raise JSRError('upstream_error', message='CDN did not provide a complete file')
    total = source.content_length
    last_update = monotonic()
    if progress:
      await progress(0, total)
    with destination.open('wb') as file:
      async for chunk in source.content.iter_chunked(_CHUNK_SIZE):
        size += len(chunk)
        if not video and size > _MAX_SUBTITLE_BYTES:
          raise JSRError('upstream_error', message='Subtitle file is too large')
        file.write(chunk)
        if progress and monotonic() - last_update >= 0.25:
          await progress(size, total)
          last_update = monotonic()
    if progress:
      await progress(size, total)


async def mux_mp4(video, subtitles, output):
  try:
    process = await asyncio.create_subprocess_exec(
      os.getenv('RZK_FFMPEG', 'ffmpeg'), '-nostdin', '-loglevel', 'error',
      '-protocol_whitelist', 'file', '-f', 'mov', '-i', str(video),
      '-protocol_whitelist', 'file', '-format_whitelist', 'srt,webvtt', '-i', str(subtitles),
      '-map', '0:v', '-map', '0:a?', '-map', '1:s:0',
      '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text',
      '-disposition:s:0', '0', '-movflags', '+faststart', str(output),
      stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
  except (OSError, NotImplementedError):
    raise JSRError('internal', message='FFmpeg is unavailable on the server') from None

  try:
    if await asyncio.wait_for(process.wait(), timeout=300) != 0:
      raise JSRError('upstream_error', message='Could not add the subtitle track to the MP4')
  except TimeoutError:
    raise JSRError('upstream_error', message='MP4 assembly timed out') from None
  finally:
    if process.returncode is None:
      try:
        process.kill()
      except ProcessLookupError:
        pass
      await process.wait()


_READY_TTL = 600


@dataclass
class ReadyMP4:
  directory: TemporaryDirectory
  filename: str
  readers: int = 0
  expired: bool = False

  @property
  def path(self):
    return Path(self.directory.name, 'output.mp4')

  def expire(self):
    self.expired = True
    if not self.readers:
      self.directory.cleanup()


class MP4Downloads:
  def __init__(self, service):
    self.service = service
    self.slot = asyncio.Semaphore(1)
    self.ready = {}
    self.expiration_tasks = set()

  async def close(self):
    tasks = tuple(self.expiration_tasks)
    for task in tasks:
      task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for file in self.ready.values():
      file.expire()
    self.ready.clear()

  async def expire(self, token, file):
    try:
      await asyncio.sleep(_READY_TTL)
    finally:
      self.ready.pop(token, None)
      file.expire()

  async def prepare(self, req, download, file_url):
    token = req.match_info['ticket']
    socket = WebSocketResponse(heartbeat=20, max_msg_size=1024)
    await socket.prepare(req)
    build = asyncio.create_task(self.build(token, download, file_url, socket))
    disconnected = asyncio.create_task(socket.receive())
    try:
      done, _ = await asyncio.wait((build, disconnected), return_when=asyncio.FIRST_COMPLETED)
      if build in done:
        await build
    finally:
      for task in (build, disconnected):
        if not task.done():
          task.cancel()
      await asyncio.gather(build, disconnected, return_exceptions=True)
      await socket.close()
    return socket

  async def build(self, token, download, file_url, socket):
    async def progress(received, total):
      await socket.send_json({'phase': 'downloading', 'received': received, 'total': total})

    directory = None
    try:
      if token not in self.ready:
        if self.slot.locked():
          raise JSRError('assembly_busy')
        async with self.slot:
          directory = TemporaryDirectory(prefix='rzk-mp4-')
          file = ReadyMP4(directory, download.filename)
          video = Path(directory.name, 'video.mp4')
          subtitles = Path(directory.name, 'subtitles')
          await socket.send_json({'phase': 'subtitles'})
          async with asyncio.timeout(900):
            await copy_source(self.service, download.subtitles, subtitles, video=False)
            await copy_source(self.service, download.video, video, video=True, progress=progress)
          await socket.send_json({'phase': 'muxing'})
          await mux_mp4(video, subtitles, file.path)
          video.unlink()
          subtitles.unlink()
          self.ready[token] = file
          task = asyncio.create_task(self.expire(token, file))
          self.expiration_tasks.add(task)
          task.add_done_callback(self.expiration_tasks.discard)
          directory = None
      await socket.send_json({'phase': 'ready', 'url': file_url})
    except (ClientError, OSError, TimeoutError, JSRError) as error:
      message = error.message if isinstance(error, JSRError) else 'Could not prepare the MP4 download'
      with suppress(ClientError, OSError):
        await socket.send_json({'phase': 'error', 'message': message})
    finally:
      if directory is not None:
        directory.cleanup()

  async def transfer(self, req):
    file = self.ready.get(req.match_info['ticket'])
    if file is None:
      raise JSRError('not_found', message='Prepared MP4 not found or expired')
    file.readers += 1
    response = None
    try:
      filename = quote(file.filename, safe='')
      with file.path.open('rb') as stream:
        response = StreamResponse(headers={
          'Content-Type': 'video/mp4',
          'Content-Length': str(file.path.stat().st_size),
          'Content-Disposition': f"attachment; filename=\"video.mp4\"; filename*=UTF-8''{filename}",
          'Cache-Control': 'no-store',
          'Referrer-Policy': 'no-referrer',
          'X-Accel-Buffering': 'no',
          'X-Content-Type-Options': 'nosniff',
        })
        await response.prepare(req)
        while chunk := stream.read(_CHUNK_SIZE):
          await response.write(chunk)
        await response.write_eof()
        return response
    except (OSError, TimeoutError):
      if response is None or not response.prepared:
        raise JSRError('upstream_error', message='Could not send the prepared MP4') from None
      if req.transport is not None:
        req.transport.abort()
      return response
    finally:
      file.readers -= 1
      if file.expired and not file.readers:
        file.directory.cleanup()
