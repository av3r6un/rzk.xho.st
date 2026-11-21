from .auth import auth
from .hdrezka import hdrezka
from .health import health
from .encoders import encoders
from .watch import watch

routes = (
  *health,
  *auth,
  *hdrezka,
  *encoders,
  *watch,
)
