from aiohttp.web_log import AccessLogger
from aiohttp.web import Application, run_app
from dotenv import load_dotenv
from .utils import middlewares
from .services.downloads import DOWNLOAD_PREFIX, download_ctx
from .services.download_sources import source_cleanup_ctx
from .config import Settings
import logging
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
    if not request.path.startswith(DOWNLOAD_PREFIX):
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
  app.cleanup_ctx.append(source_cleanup_ctx)
  if os.getenv('DEBUG', False):
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
