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
