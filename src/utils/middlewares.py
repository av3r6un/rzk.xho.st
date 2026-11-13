from aiohttp.web import json_response, middleware, StreamResponse, HTTPException, Request
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from jwt import ExpiredSignatureError, InvalidTokenError
from aiohttp.web_exceptions import HTTPNotFound
from src.services import AuthService
from .jwt import decode_token
from src.exceptions import JSRError
from src.services.downloads import DOWNLOAD_ROUTES
import inspect
import logging


@middleware
async def db_middleware(req: Request, handler, *args, **kwargs):
  if req.match_info.route.name in DOWNLOAD_ROUTES:
    return await handler(req, *args, **kwargs)
  session_factory: async_sessionmaker[AsyncSession] = req.app['db_sessionmaker']
  async with session_factory() as session:
    try:
      req['session'] = session
      response = await handler(req, *args, **kwargs)
      if getattr(response, 'status', 200) >= 400:
        await session.rollback()
      else:
        await session.commit()
      return response
    except HTTPNotFound:
      await session.rollback()
      return json_response(dict(status='error', message='Requested page is not found'), status=404)
    except Exception:
      await session.rollback()
      raise


@middleware
async def params_middleware(request, handler):
  params: dict[str, str | list[str]] = {}

  for key in dict.fromkeys(request.query.keys()):
    values = request.query.getall(key)
    params[key] = values if len(values) > 1 else values[0]

  request['params'] = params
  return await handler(request)


@middleware
async def response_middleware(req: Request, handler, *args, **kwargs):
  try:
    call_kwargs = {}
    try:
      sig = inspect.signature(handler)
      params = sig.parameters
      if 'session' in params or any(p.kind == p.VAR_KEYWORD for p in params.values()):
        call_kwargs['session'] = req.get('session')
    except (TypeError, ValueError):
      pass
  
    result = await handler(req, *args, **call_kwargs, **kwargs)
    if isinstance(result, StreamResponse):
      return result
    if isinstance(result, tuple):
      body, message = result
      if isinstance(message, int) and not isinstance(message, bool):
        return json_response(dict(status='success' if message < 400 else 'error', body=body), status=message)
      return json_response(dict(status='success', body=body, message=message))
    return json_response(dict(status='success', body=result))
  except JSRError as e:
    return json_response(**e.json)
  except HTTPException:
    raise
  except Exception as ex:
    logging.exception('Unhandled request error')
    return json_response(dict(status='error', message=str(ex)), status=500)

 
@middleware
async def jwt_middleware(req: Request, handler, *args, **kwargs):
  from src import settings

  route_error = getattr(req.match_info, 'http_exception', None)
  if isinstance(route_error, HTTPNotFound):
    raise route_error
  
  route = req.match_info.route
  if route.name in DOWNLOAD_ROUTES:
    return await handler(req)
  session = req['session']
  if route.name in {'auth_login', 'auth_register'} or any(
    req.path == path or req.path.startswith(path + '/') for path in settings.NOT_SECURED_PATHS
  ):
    return await handler(req, session=session)
  
  auth_header = req.headers.get('Authorization')
  if not auth_header or not auth_header.startswith('Bearer '):
    raise JSRError('missing_auth_header')
  
  token = auth_header.split(' ')[1]
  try:
    payload = decode_token(token, 'refresh' if route.name == 'auth_refresh' else 'access')
    user = await AuthService.get_user(session, payload['sub'])
    if not user or not user.password:
      raise JSRError('unauthorized')
    req['current_user'] = user
    req['token_claims'] = payload
    
  except ExpiredSignatureError: raise JSRError('token_expired')
  except InvalidTokenError: raise JSRError('invalid_token')
  
  return await handler(req, session=session)

middlewares = [db_middleware, params_middleware, response_middleware, jwt_middleware]
