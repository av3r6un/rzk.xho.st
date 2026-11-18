from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text
from src.exceptions import JSRError

from .base import Base
import re


cookie_pair = re.compile(
  r"[!#$%&'*+\-.^_\x60|~0-9A-Za-z]+="
  r'(?:[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*'
  r'|"[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*")'
)

class User(Base):
  __tablename__ = 'users'

  uid: Mapped[str] = mapped_column(String(6), primary_key=True)
  username: Mapped[str | None] = mapped_column(String(50), nullable=False, unique=True, index=True)
  email: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
  password: Mapped[str | None] = mapped_column(String(255), nullable=True)

  hdrezka_cookies: Mapped[str | None] = mapped_column(Text, nullable=True)

  avatar: Mapped[str] = mapped_column(String(255), nullable=True)

  def __init__(self, uid, username, password, **kwargs) -> None:
    self.uid = uid
    self.username = username
    self.email = kwargs.get('email', None)
    self.password = password
    
    
  @property
  def cookies(self):
    return self.hdrezka_cookies
  
  @cookies.setter
  def cookies(self, value):
    pairs = [pair.strip(' \t') for pair in value.split(';')]
    if not all(cookie_pair.fullmatch(pair) for pair in pairs):
      raise JSRError('invalid_payload')
  
    self.hdrezka_cookies = '; '.join(pairs)

  @property
  def json(self):
    return dict(uid=self.uid, username=self.username, email=self.email, avatar=self.avatar)

  def __str__(self):
    return f'<User {self.uid}>'
