from datetime import datetime as dt, timedelta as delta, timezone
from src.exceptions import JSRError
import bcrypt
import jwt
import os


ALG = 'HS256'

def _create_token(user_uid: str, token_type: str, expired_delta: delta, **claims):
  payload = dict(sub=user_uid, token_type=token_type, exp=dt.now(timezone.utc) + expired_delta, **claims)
  if not os.getenv('SECRET_KEY', None):
    raise JSRError('not_found', message='Essential settings is not filled!')
  return jwt.encode(payload, os.getenv('SECRET_KEY'), algorithm=ALG)

def decode_token(token: str, token_type: str):
  payload = jwt.decode(token, os.environ['SECRET_KEY'], algorithms=[ALG],
                       options={'require': ['sub', 'exp', 'token_type']})
  if payload['token_type'] != token_type:
    raise jwt.InvalidTokenError('Incorrect token type')
  return payload

def create_token(user_uid: str, fresh: bool = True):
  if fresh:
    ttl = int(os.getenv('JWT_TOKEN_EXPIRES', '900'))
    return _create_token(user_uid, 'access', delta(seconds=ttl))
  refresh_ttl = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', '2592000'))
  return _create_token(user_uid, 'refresh', delta(seconds=refresh_ttl))


def hash_password(password: str) -> str:
  return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_pw(password: str, hash: str) -> bool:
  return bcrypt.checkpw(password.encode(), hash.encode())
