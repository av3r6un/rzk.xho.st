from aiohttp.web_log import AccessLogger
from aiohttp.web import Application, run_app
from dotenv import load_dotenv
from .utils import middlewares
from .services.downloads import DOWNLOAD_PREFIX, download_ctx
from .services.watch import WATCH_PREFIX, watch_ctx, watch_debug_enabled
from .services.download_sources import source_cleanup_ctx
from .modules.ffmpeg_encoders import encoder_checks_ctx
from .config import Settings
import logging
import re
import sys
import os


load_dotenv('.env')

settings = Settings()

LOG_FILENAME = 'logs/all.log'

  
async def db_ctx(app: Application):
  from .utils.engine import session_maker, dispose
  app['db_sessionmaker'] = session_maker
  yield
  await dispose()
  
class RedactedAccessLogger(AccessLogger):
  def log(self, request, response, elapsed):
    if request.path.startswith(WATCH_PREFIX):
      _, _, resource = request.path[len(WATCH_PREFIX):].partition('/')
      if watch_debug_enabled() and re.fullmatch(r'master\.m3u8|subs/[0-9]+/(?:index\.m3u8|full\.vtt)', resource):
        self.logger.info('AirPlay %s %s -> %s [%s]', request.method, resource, response.status,
                         request.headers.get('User-Agent', '')[:160])
    elif not request.path.startswith(DOWNLOAD_PREFIX):
      super().log(request, response, elapsed)


def create_app():
  from .routes import routes
  app = Application(middlewares=middlewares)
  logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] WEB: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=LOG_FILENAME
  )
  app.add_routes(routes)
  app.cleanup_ctx.append(db_ctx)
  app.cleanup_ctx.append(download_ctx)
  app.cleanup_ctx.append(watch_ctx)
  app.cleanup_ctx.append(source_cleanup_ctx)
  app.cleanup_ctx.append(encoder_checks_ctx)
  console = logging.StreamHandler()
  console.setLevel(logging.INFO)
  console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] WEB: %(message)s", "%Y-%m-%d %H:%M:%S"))
  logging.getLogger().addHandler(console)
  
  return app

def start():
  run_app(
    create_app(),
    host='0.0.0.0',
    port=int(os.getenv('APP_PORT', '8090')),
    handler_cancellation=True,
    access_log_class=RedactedAccessLogger,
    access_log_format='%{X-Forwarded-For}i %s - "%r" (%b | %D) %{User-Agent}i',
  )
