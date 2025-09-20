from pathlib import Path
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from alembic.script import ScriptDirectory
from alembic.config import Config
from alembic.util.exc import CommandError


class DatabaseVersionError(Exception):
    pass


def get_latest_revision() -> str | None:
    """Get the latest revision from alembic versions directory."""
    db_dir = Path(__file__).parent
    alembic_config_file = db_dir / "alembic.ini"
    config = Config(alembic_config_file)
    config.set_main_option("script_location", str(db_dir / "alembic"))
    script = ScriptDirectory.from_config(config)

    # Get the head revision (latest)
    return script.get_current_head()


def get_database_revision(session: Session) -> Optional[str]:
    """Get current revision from the database's alembic_version table."""
    try:
        result = session.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        return row[0] if row else None
    except Exception:
        # Table doesn't exist (new database)
        return None


def needs_migration(session: Session) -> bool:
    """Check if database needs migration to latest revision."""
    current_revision = get_database_revision(session)
    latest_revision = get_latest_revision()

    # New database (no alembic_version table) needs migration
    # Or different revision needs migration
    return current_revision != latest_revision


def is_legacy_database(session: Session) -> bool:
    """Check if database has schema but no alembic versioning (legacy database)."""
    # Check if alembic_version table exists
    has_alembic_version = get_database_revision(session) is not None

    if has_alembic_version:
        return False

    # Check if database has tables (indicating it's not empty/legacy)
    try:
        # Check for a key table that should exist in legacy databases
        result = session.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'"
            )
        )
        has_workflow_table = result.fetchone() is not None
        return has_workflow_table
    except Exception:
        return False


def get_legacy_database_revision(session: Session) -> str:
    """Determine appropriate revision for legacy database based on schema."""
    try:
        # Check if snkmt_db_version table exists
        result = session.execute(text("PRAGMA table_info(snkmt_db_version)"))
        columns = [row[1] for row in result.fetchall()]  # row[1] is column name

        if columns:  # Table exists - corresponds to a088a7b93fe5
            # Legacy databases with snkmt_db_version table (regardless of timestamp column)
            # should be stamped as a088a7b93fe5 since that's where the migration chain begins
            return "a088a7b93fe5"
        else:
            # No snkmt_db_version table - also corresponds to a088a7b93fe5
            return "a088a7b93fe5"
    except Exception:
        # If any error checking, assume oldest revision
        return "a088a7b93fe5"


def is_database_newer_than_code(session: Session) -> bool:
    """Check if database is newer than what this code supports."""
    current_revision = get_database_revision(session)
    if not current_revision:
        return False

    latest_revision = get_latest_revision()

    # If they match, database is not newer
    if current_revision == latest_revision:
        return False

    # Simple heuristic: if current revision is not in our known revisions,
    # it's likely from a newer version of the code
    db_dir = Path(__file__).parent
    alembic_config_file = db_dir / "alembic.ini"
    config = Config(alembic_config_file)
    config.set_main_option("script_location", str(db_dir / "alembic"))
    script = ScriptDirectory.from_config(config)

    try:
        # Try to get the revision - if it doesn't exist in our migration files,
        # it's likely from a newer version
        script.get_revision(current_revision)
        return False  # Revision exists, so it's not newer than our code
    except CommandError:
        # Unknown revision - likely from newer version of snkmt
        return True


def stamp_legacy_database(session: Session, db_path: str) -> str:
    """Auto-stamp legacy database with appropriate revision."""
    from alembic.command import stamp
    from alembic.config import Config

    # Determine which revision to stamp with
    revision = get_legacy_database_revision(session)

    # Set up Alembic configuration
    db_dir = Path(__file__).parent
    alembic_config_file = db_dir / "alembic.ini"
    alembic_script_location = db_dir / "alembic"

    config = Config(str(alembic_config_file))
    config.set_main_option("script_location", str(alembic_script_location))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    try:
        stamp(config, revision)
        return revision
    except Exception as e:
        raise DatabaseVersionError(f"Failed to stamp legacy database: {e}") from e
