from src.modules.ffmpeg_encoders import ENCODER_CHECKS, ENCODER_NAME
from aiohttp.web import Request, RouteTableDef
from src.models import ActiveEncoder
from src.exceptions import JSRError

encoders = RouteTableDef()


@encoders.get('/api/ffmpeg/encoders')
async def get_encoders(req: Request, session):
  enc = await ActiveEncoder.all(session)
  return [a.json for a in enc]


@encoders.patch('/api/ffmpeg/encoders')
async def refresh_encoders(req: Request, *args, **kwargs):
  req.app[ENCODER_CHECKS].refresh()
  return dict(refresh='schedules'), 202


@encoders.put('/api/ffmpeg/encoders')
async def add_encoder(req: Request, session):
  data = req['request_data']
  if not ENCODER_NAME.fullmatch(data.get('name')):
    raise JSRError('invalid_payload')
  await session.rollback()
  checks = req.app[ENCODER_CHECKS]
  added = await checks.register([data.get('name')])
  checks.refresh(added=added)
  return dict(name=data.get('name'), refresh='scheduled'), 202
