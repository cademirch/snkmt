from typing import Any
from snkmt.core.models.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from datetime import datetime, timezone

# db versioning adapted from https://github.com/insitro/redun/blob/main/redun/backends/db/__init__.py
DB_UNKNOWN_VERSION = 99


class DBVersion(Base):
    """
    Database version
    """

    __tablename__ = "snkmt_db_version"
    id: Mapped[str] = mapped_column(
        String, primary_key=True
    )  # this can just be the alembic revision id
    major: Mapped[int] = mapped_column()
    minor: Mapped[int] = mapped_column()
    timestamp: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __lt__(self, other) -> bool:
        if not isinstance(other, DBVersion):
            raise TypeError(f"Expected DBVersion: {other}")
        return (self.major, self.minor) < (other.major, other.minor)

    def __le__(self, other) -> bool:
        if not isinstance(other, DBVersion):
            raise TypeError(f"Expected DBVersion: {other}")
        return (self.major, self.minor) <= (other.major, other.minor)

    def __gt__(self, other) -> bool:
        if not isinstance(other, DBVersion):
            raise TypeError(f"Expected DBVersion: {other}")
        return (self.major, self.minor) > (other.major, other.minor)

    def __ge__(self, other) -> bool:
        if not isinstance(other, DBVersion):
            raise TypeError(f"Expected DBVersion: {other}")
        return (self.major, self.minor) >= (other.major, other.minor)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DBVersion):
            raise TypeError(f"Expected DBVersion: {other}")
        return (self.major, self.minor) == (other.major, other.minor)

    def __str__(self) -> str:
        if self.minor == DB_UNKNOWN_VERSION:
            return f"{self.major}.?"
        else:
            return f"{self.major}.{self.minor}"

    def __repr__(self) -> str:
        return f"DBVersion(id={self.id},major={self.major},minor={self.minor})"
