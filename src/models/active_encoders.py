from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ActiveEncoder(Base):
  __tablename__ = 'active_encoders'

  name: Mapped[str] = mapped_column(String(64), primary_key=True)
  available: Mapped[bool | None]
  working: Mapped[bool | None]
  checked_at: Mapped[int | None] = mapped_column(BigInteger)
  error: Mapped[str | None] = mapped_column(String(512))
