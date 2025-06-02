from typing import Any
from snkmt.db.models.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from datetime import datetime, timezone

# db versioning adapted from https://github.com/insitro/redun/blob/main/redun/backends/db/__init__.py
DB_UNKNOWN_VERSION = 99


class DBVersionError(Exception):
    pass


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


# List of all available database versions and migrations.
# Note these are sorted from oldest to newest.
null_db_version = DBVersion(id="000000000000", major=-1, minor=0)
DB_VERSIONS = [DBVersion(id="a088a7b93fe5", major=1, minor=0)]
DB_MIN_VERSION = DBVersion(id="", major=1, minor=0)  # Min db version needed by snkmt.
DB_MAX_VERSION = DBVersion(id="", major=1, minor=0)  # Max db version needed by snkmt.


def parse_db_version(version_str: str) -> DBVersion:
    """
    Parses a db version string such as "2.0" or "3" into a DBVersion.
    """
    if version_str == "latest":
        return DB_VERSIONS[-1]

    dots = version_str.count(".")
    if dots == 0:
        major, minor = (int(version_str), 0)
    elif dots == 1:
        major, minor = tuple(map(int, version_str.split(".")))
    else:
        raise ValueError(f"Invalid db version format: {version_str}")

    for version in DB_VERSIONS:
        if version.major == major and version.minor == minor:
            return version

    raise DBVersionError(f"Unknown db version: {version_str}")
