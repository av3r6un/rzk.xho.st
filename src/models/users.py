from typing import List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text

from .base import Base


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
  def json(self):
    return dict(uid=self.uid, username=self.username, email=self.email, avatar=self.avatar)

  def __str__(self):
    return f'<User {self.uid}>'
