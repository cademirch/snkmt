from snkmt.core.models.version import DBVersion


class DBVersionError(Exception):
    pass


# List of all available database versions and migrations.
# Note these are sorted from oldest to newest.
null_db_version = DBVersion(id="000000000000", major=-1, minor=0)
DB_VERSIONS = [
    DBVersion(id="a088a7b93fe5", major=1, minor=0),
    DBVersion(id="c59016d243cc", major=1, minor=1),
]
DB_MIN_VERSION = DBVersion(
    id="a088a7b93fe5", major=1, minor=0
)  # Min db version needed by snkmt.
DB_MAX_VERSION = DBVersion(
    id="c59016d243cc", major=1, minor=1
)  # Max db version needed by snkmt.


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
