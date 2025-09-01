import pytest

from pathlib import Path
from snkmt.core.db.session import Database, AsyncDatabase
from snkmt.core.models.version import DBVersion
from snkmt.core.db.version import parse_db_version, DB_VERSIONS
import tempfile
import sys

@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / "test.db"

@pytest.fixture
async def async_db(temp_db_path):
    """Create and initialize an async database."""
    db = AsyncDatabase(db_path=str(temp_db_path), create_db=True)
    await db.initialize()
    yield db
    await db.close()

def test_new_database_sets_latest_version(temp_db_path):
    """Test that a new database is set to the latest version."""

    db = Database(db_path=str(temp_db_path), create_db=True)

    actual_version = db.get_version()
    expected_version = parse_db_version("latest")

    assert actual_version == expected_version

@pytest.mark.asyncio
async def test_async_new_database_sets_latest_version(temp_db_path):
    """Test that a new async database is set to the latest version."""
    db = AsyncDatabase(db_path=str(temp_db_path), create_db=True)
    await db.initialize()

    actual_version = await db.get_version()
    expected_version = parse_db_version("latest")

    assert actual_version == expected_version
    await db.close()


@pytest.mark.asyncio
async def test_async_database_creates_file(temp_db_path):
    """Test that AsyncDatabase creates a database file."""
    assert not temp_db_path.exists()

    db = AsyncDatabase(db_path=str(temp_db_path), create_db=True)
    await db.initialize()

    assert temp_db_path.exists()
    await db.close()


@pytest.mark.asyncio
async def test_async_database_raises_when_not_found():
    """Test that AsyncDatabase raises error when db doesn't exist and create_db=False."""
    from snkmt.core.db.session import DatabaseNotFoundError

    with tempfile.TemporaryDirectory() as temp_dir:
        fake_path = Path(temp_dir) / "nonexistent.db"

        with pytest.raises(DatabaseNotFoundError):
            _db = AsyncDatabase(db_path=str(fake_path), create_db=False)


@pytest.mark.asyncio
async def test_async_database_raises_on_outdated_version(temp_db_path):
    """Test that AsyncDatabase raises DBVersionError when database version is outdated."""
    from snkmt.core.db.version import DBVersionError, DB_VERSIONS

    # First, create a database with an old version
    db_sync = Database(
        db_path=str(temp_db_path),
        create_db=True,
        auto_migrate=False,
        ignore_version=True,
    )

    # Manually set an old version
    old_version = DB_VERSIONS[0]  # Get the first (oldest) version
    latest_version = DB_VERSIONS[-1]

    # Clear any existing version and set to old version
    db_sync.session.query(DBVersion).delete()
    db_sync.session.add(
        DBVersion(
            id=old_version.id,
            major=old_version.major,
            minor=old_version.minor,
        )
    )
    db_sync.session.commit()
    db_sync.session.close()

    # Now try to open with AsyncDatabase - should raise DBVersionError
    db_async = AsyncDatabase(db_path=str(temp_db_path), create_db=False)

    with pytest.raises(DBVersionError) as exc_info:
        await db_async.initialize()

    error_msg = str(exc_info.value)
    assert str(old_version) in error_msg
    assert str(latest_version) in error_msg
    assert "Auto-migration not supported in async" in error_msg
    assert "snkmt db migrate" in error_msg

    await db_async.close()


@pytest.mark.asyncio
async def test_db_migrate_command(temp_db_path):
    """Test that the db migrate command upgrades database version."""
    from typer.testing import CliRunner
    from snkmt import app
    from snkmt.core.db.version import DB_VERSIONS

    runner = CliRunner()

    # Create database with old version
    old_version = DB_VERSIONS[0]
    latest_version = DB_VERSIONS[-1]
    print(f"{old_version=} {latest_version=}")
    db = Database(
        db_path=str(temp_db_path),
        create_db=True,
        auto_migrate=False,
        ignore_version=True,
    )

    # Clear any version and set to old
    db.session.query(DBVersion).delete()
    db.session.add(
        DBVersion(
            id=old_version.id,
            major=old_version.major,
            minor=old_version.minor,
        )
    )
    db.session.commit()

    # Verify it's at old version
    assert db.get_version() == old_version
    db.session.close()

    # Run migrate command
    result = runner.invoke(app, ["db", "migrate", str(temp_db_path)])
    if result.exit_code != 0:
        print(f"Exception: {result.exception}")
        print(result.output)

    assert result.exit_code == 0

    # Verify database is now at latest version
    db_after = Database(
        db_path=str(temp_db_path),
        create_db=False,
        auto_migrate=False,
        ignore_version=True,
    )
    current_version = db_after.get_version()
    assert current_version == latest_version
    db_after.session.close()


def test_db_model():
    """Test DBVersion model comparison operators and string representation."""
    v1_0 = DBVersion(id="test1", major=1, minor=0)
    v1_1 = DBVersion(id="test2", major=1, minor=1)
    v2_0 = DBVersion(id="test3", major=2, minor=0)
    v1_0_duplicate = DBVersion(id="test4", major=1, minor=0)
    v_unknown = DBVersion(id="test5", major=1, minor=99)  # DB_UNKNOWN_VERSION

    # Test equality
    assert v1_0 == v1_0_duplicate
    assert not (v1_0 == v1_1)

    # Test less than
    assert v1_0 < v1_1
    assert v1_1 < v2_0
    assert not (v1_1 < v1_0)

    # Test less than or equal
    assert v1_0 <= v1_0_duplicate
    assert v1_0 <= v1_1
    assert not (v1_1 <= v1_0)

    # Test greater than
    assert v1_1 > v1_0
    assert v2_0 > v1_1
    assert not (v1_0 > v1_1)

    # Test greater than or equal
    assert v1_0 >= v1_0_duplicate
    assert v1_1 >= v1_0
    assert not (v1_0 >= v1_1)

    # Test string representation
    assert str(v1_0) == "1.0"
    assert str(v1_1) == "1.1"
    assert str(v2_0) == "2.0"
    assert str(v_unknown) == "1.?"

    # Test TypeError for invalid comparisons
    with pytest.raises(TypeError):
        v1_0 < "not_a_version"

    with pytest.raises(TypeError):
        v1_0 == "not_a_version"
