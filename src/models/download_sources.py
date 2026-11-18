from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DownloadSource(Base):
  __tablename__ = 'download_sources'
  __table_args__ = (
    Index('ix_download_sources_selection', 'user_uid', 'media_uid', 'translator_id', 'season', 'episode'),
  )

  uid: Mapped[str] = mapped_column(String(14), primary_key=True)
  user_uid: Mapped[str] = mapped_column(ForeignKey('users.uid', ondelete='CASCADE'))
  media_uid: Mapped[str] = mapped_column(ForeignKey('media.uid', ondelete='CASCADE'))
  batch_uid: Mapped[str] = mapped_column(String(14))
  entity_type: Mapped[str] = mapped_column(String(9))
  title: Mapped[str] = mapped_column(Text)
  url: Mapped[str] = mapped_column(Text)
  reserve: Mapped[str | None] = mapped_column(Text)
  expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
  reserve_expires_at: Mapped[int | None] = mapped_column(BigInteger)
  translator_id: Mapped[int | None] = mapped_column(Integer)
  position: Mapped[int | None] = mapped_column(Integer)
  season: Mapped[int | None] = mapped_column(Integer)
  episode: Mapped[int | None] = mapped_column(Integer)

  def __init__(self, uid, user_uid, media_uid, batch_uid, entity_type, title, url, expires_at, translator_id, **kwargs) -> None:
    self.uid = uid
    self.user_uid = user_uid
    self.media_uid = media_uid
    self.batch_uid = batch_uid
    self.entity_type = entity_type
    self.title = title
    self.url = url
    self.reserve = kwargs.get('reserve')
    self.expires_at = expires_at
    self.reserve_expires_at = kwargs.get('reserve_expires_at')
    self.translator_id = translator_id
    self.position = kwargs.get('position')
    self.season = kwargs.get('season')
    self.episode = kwargs.get('episode')
    
  @property
  def json(self):
    return dict(
      uid=self.uid, media_uid=self.media_uid, user_uid=self.user_uid, batch_uid=self.batch_uid, entity_type=self.entity_type,
      title=self.titlt, url=self.url, reserve=self.reserve, expires_at=self.expires_at, reserve_expires_at=self.reserve_expires_at,
      translator_id=self.translator_id, position=self.position, season=self.season, episode=self.episode
    )
