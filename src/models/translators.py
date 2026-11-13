from sqlalchemy import ForeignKey, String, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Translator(Base):
  __tablename__ = 'translators'
  
  uid: Mapped[str] = mapped_column(String(10), primary_key=True)
  id: Mapped[int] = mapped_column(Integer, unique=True)
  name: Mapped[str | None] = mapped_column(String(50), nullable=True)
  
  def __init__(self, uid, id, name, **kwargs) -> None:
    self.uid = uid
    self.id = id
    self.name = name
      
  @property
  def json(self):
    return dict(uid=self.uid, id=self.id, name=self.name)
  
  
class MediaTranslator(Base):
  __tablename__ = 'media_translators'
  __table_args__ = (UniqueConstraint('media_uid', 'translator_uid'),)
  
  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  media_uid: Mapped[str] = mapped_column(String(32), ForeignKey('media.uid'), nullable=False)
  translator_uid: Mapped[str] = mapped_column(String(10), ForeignKey('translators.uid'), nullable=False)
  
  def __init__(self, media_uid, translator_uid) -> None:
    self.media_uid = media_uid
    self.translator_uid = translator_uid
