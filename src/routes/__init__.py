from .auth import auth
from .hdrezka import hdrezka
from .health import health

routes = (
  *health,
  *auth,
  *hdrezka,
)
