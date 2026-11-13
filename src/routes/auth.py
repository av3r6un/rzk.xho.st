from json import JSONDecodeError
from sqlalchemy.ext.asyncio import AsyncSession
from aiohttp.web import RouteTableDef, Request
from src.exceptions import JSRError
from src.services import AuthService

auth = RouteTableDef()


@auth.post('/auth/', name='auth_login')
async def login(req: Request, session: AsyncSession):
  try:
    payload = await req.json()
  except (JSONDecodeError, UnicodeError):
    raise JSRError('invalid_payload')
  data = payload.get('data') if isinstance(payload, dict) else None
  if not isinstance(data, dict):
    raise JSRError('invalid_payload')
  username, password = data.get('username'), data.get('password')

  return await AuthService.login(session, username, password)


@auth.post('/auth/refresh', name='auth_refresh')
async def refresh(req: Request, session: AsyncSession):
  return AuthService.refresh(req['current_user'].uid)


@auth.post('/auth/register', name='auth_register')
async def register(req: Request, session: AsyncSession):
  try:
    payload = await req.json()
  except (JSONDecodeError, UnicodeError):
    raise JSRError('invalid_payload')
  data = payload.get('data') if isinstance(payload, dict) else None
  if not isinstance(data, dict):
    raise JSRError('invalid_payload')
  return await AuthService.register(
    session, password=data.get('password'), username=data.get('username')
  ), 202


@auth.get('/auth/me')
async def get_me(req: Request, session: AsyncSession):
  return req['current_user'].json
