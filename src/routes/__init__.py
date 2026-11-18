from .auth import auth
from .hdrezka import hdrezka
from .health import health
from .encoders import encoders

routes = (
  *health,
  *auth,
  *hdrezka,
  *encoders,
)
