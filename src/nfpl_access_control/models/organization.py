"""NFPL organizational reference data."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfpl_access_control.db.base import Base
from nfpl_access_control.models.base import TimestampMixin, UuidPrimaryKeyMixin


class Branch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "branches"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    jobs = relationship("Job", back_populates="branch")


class Client(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    jobs = relationship("Job", back_populates="client")
