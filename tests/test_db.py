from re import S
import pytest

from pathlib import Path

from snkmt.core.db.session import Database, AsyncDatabase
from snkmt.core.db.version import (
    get_database_revision,
    get_latest_revision,
    get_legacy_database_revision,
    is_legacy_database,
    stamp_legacy_database,
)
import tempfile
import sys

from pytest_loguru.plugin import caplog


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / "test.db"


@pytest.fixture
async def async_db(temp_db_path):
    """Create an async database."""
    db = AsyncDatabase(db_path=str(temp_db_path), create_db=True)
    yield db
    await db.close()


def test_new_database_sets_latest_revision(temp_db_path):
    """Test that a new database is set to the latest revision."""

    db = Database(db_path=str(temp_db_path), create_db=True)

    actual_revision = db.get_revision()
    expected_revision = get_latest_revision()

    assert actual_revision == expected_revision


def test_new_database_creates_expected_tables(temp_db_path):
    """Test that a new database creates all expected tables."""
    db = Database(db_path=str(temp_db_path), create_db=True)
    
    # Get table info from the database
    db_info = db.get_db_info()
    tables = db_info["tables"]
    
    # Expected tables based on our models + alembic version table
    expected_tables = {
        "workflows",
        "rules", 
        "jobs",
        "files",
        "errors",
        "alembic_version"  # Alembic creates this table for version tracking
    }
    
    # Convert to set for easier comparison
    actual_tables = set(tables)
    
    # Check that all expected tables exist
    assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"
    
    # Check that we don't have unexpected tables (allow extra tables but log them)
    extra_tables = actual_tables - expected_tables
    if extra_tables:
        print(f"Found extra tables (this might be okay): {extra_tables}")
    
    db.close()


@pytest.mark.asyncio
async def test_async_new_database_sets_latest_revision(temp_db_path):
    """Test that a new async database is set to the latest revision."""
    db = AsyncDatabase(db_path=str(temp_db_path), create_db=True)

    actual_revision = db.get_revision()  # Now sync method
    expected_revision = get_latest_revision()

    assert actual_revision == expected_revision
    await db.close()


@pytest.mark.asyncio
async def test_async_database_creates_file(temp_db_path):
    """Test that AsyncDatabase creates a database file."""
    assert not temp_db_path.exists()

    db = AsyncDatabase(db_path=str(temp_db_path), create_db=True)

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
async def test_async_database_auto_migrates_outdated_revision(temp_db_path):
    """Test that AsyncDatabase auto-migrates when database revision is outdated."""
    from alembic.command import upgrade, downgrade
    from alembic.config import Config as AlembicConfig
    from pathlib import Path

    # First, create a database at latest revision
    db_sync = Database(
        db_path=str(temp_db_path),
        create_db=True,
        auto_migrate=True,
    )
    db_sync.close()

    # Set up Alembic and downgrade to old revision
    db_dir = Path(__file__).parent.parent / "src" / "snkmt" / "core" / "db"
    config = AlembicConfig(db_dir / "alembic.ini")
    config.set_main_option("script_location", str(db_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{temp_db_path}")

    # Downgrade to old revision
    old_revision = "a088a7b93fe5"  # First revision from our migration history
    downgrade(config, old_revision)

    # Now create AsyncDatabase - it should auto-migrate via sync database
    db_async = AsyncDatabase(db_path=str(temp_db_path), create_db=False)

    # Should be at latest revision after auto-migration
    latest_revision = get_latest_revision()
    assert db_async.get_revision() == latest_revision

    await db_async.close()


def test_database_revision_functions():
    """Test the new revision-based functions."""
    from snkmt.core.db.version import get_latest_revision

    # Test that we can get the latest revision
    latest = get_latest_revision()
    assert latest is not None
    assert isinstance(latest, str)
    assert len(latest) == 12  # Alembic revision IDs are 12 characters


def test_legacy_database(temp_db_path, caplog):
    """
    this was the only database revision that made it to releases 0.1.0 to 0.1.2
    """

    import logging
    import shutil

    legacy_db = Path("tests/fixtures/legacy.db")
    test_db = Path(temp_db_path)
    shutil.copy(legacy_db, test_db)

    with caplog.at_level(logging.INFO):
        db = Database(
            db_path=str(temp_db_path),
            create_db=False,
            auto_migrate=True,
            ignore_version=False,
        )

        desired_rev = "a088a7b93fe5"

        assert (
            "Legacy database detected - auto-stamping with appropriate revision"
            in caplog.text
        )

        assert f"Legacy database stamped with revision: {desired_rev}" in caplog.text
