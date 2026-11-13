from sqlalchemy.exc import IntegrityError
from src.utils.jwt import check_pw, create_token, hash_password
from src.exceptions import JSRError
from src.models import User
import asyncio


class AuthService:
  @classmethod
  async def register(cls, session, *, password, username, email=None) -> dict:
    try:
      if not 1 <= len(password.encode('utf-8')) <= 72:
        raise JSRError('invalid_payload')
      password_hash = await asyncio.to_thread(hash_password, password)
    except UnicodeEncodeError:
      raise JSRError('invalid_payload')

    user = User(await User.create_uid(session), username, password_hash, email=email)
    session.add(user)
    try:
      await session.flush()
    except IntegrityError:
      raise JSRError('conflict', message='Account already exists')

    return cls._login_response(user)

  @classmethod
  async def get_user(cls, session, uid) -> User | None:
    return await User.first(session, uid=uid)

  @classmethod
  async def login(cls, session, username, password) -> dict:
    user = await User.first(session, username=username)
    if not user or not user.password or not await asyncio.to_thread(check_pw, password, user.password):
      raise JSRError('unauthorized', message='Incorrect email or password')

    return cls._login_response(user)

  @staticmethod
  def _login_response(user: User) -> dict:
    return dict(**user.json, access_token=create_token(user.uid),
                refresh_token=create_token(user.uid, fresh=False))

  @classmethod
  def refresh(cls, uid) -> dict:
    return dict(access_token=create_token(uid))
