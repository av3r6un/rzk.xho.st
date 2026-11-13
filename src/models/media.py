from sqlalchemy import ForeignKey, String, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Media(Base):
  __tablename__ = 'media'

  uid: Mapped[str] = mapped_column(String(32), primary_key=True)
  path: Mapped[str] = mapped_column(String(1024))
  id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
  kp_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
  imdb_id: Mapped[str | None] = mapped_column(String(15), nullable=True) 
  category: Mapped[str] = mapped_column(String(16))
  name: Mapped[str | None] = mapped_column(String(150), nullable=True)
  original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
  cover: Mapped[str] = mapped_column(String(255), nullable=True)
  slogan: Mapped[str] = mapped_column(String(100), nullable=True)
  description: Mapped[str | None] = mapped_column(Text, nullable=True)
  release: Mapped[int | None] = mapped_column(Integer, nullable=True)
  country: Mapped[str] = mapped_column(String(100), nullable=True)
  genres: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
  
  @property
  def json(self):
    return dict(
      uid=self.uid, id=self.id, external_ids=self.external_ids,
      category=self.category, name=self.name, original_name=self.original_name, cover=self.cover,
      slogan=self.slogan, description=self.description, release=self.release, country=self.country,
      genres=self.genres
    )
  
  @property
  def external_ids(self):
    return dict(imdb_id=self.imdb_id, kp_id=self.kp_id)
  
  @external_ids.setter
  def external_ids(self, value):
    self.imdb_id = value.get('imdb_id')
    self.kp_id = value.get('kp_id')


class SearchHistory(Base):
  __tablename__ = 'search_history'
  __table_args__ = (UniqueConstraint('user_uid', 'media_uid'),)

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  user_uid: Mapped[str] = mapped_column(ForeignKey('users.uid'))
  media_uid: Mapped[str] = mapped_column(ForeignKey('media.uid'))
