import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from loguru import logger
from snkmt.core.db.version import (
    DatabaseVersionError,
    get_latest_revision,
    get_database_revision,
    needs_migration,
    is_database_newer_than_code,
    is_legacy_database,
    stamp_legacy_database,
)
import subprocess
from snkmt.core.repository.sql import SQLAlchemyWorkflowRepository
from snkmt.core.db import SNKMT_DIR


logger.remove()
logger.add(sys.stderr)


class DatabaseNotFoundError(Exception):
    """Raised when the Snakemake DB file isn’t found and creation is disabled."""

    pass


class Database:
    """Simple connector for the Snakemake SQLite DB."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        create_db: bool = True,
        auto_migrate: bool = True,
        ignore_version: bool = False,
    ):
        default_db_path = SNKMT_DIR / "snkmt.db"

        if db_path:
            db_file = Path(db_path).resolve()
        else:
            db_file = default_db_path.resolve()

        if not db_file.parent.exists():
            if create_db:
                db_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                raise DatabaseNotFoundError(f"No DB directory: {db_file.parent}")

        if not db_file.exists() and not create_db:
            raise DatabaseNotFoundError(f"DB file not found: {db_file}")

        self.db_path = str(db_file)  # Always absolute path
        self.db_file = db_file  # Keep Path object for config registration

        # Register database in config
        self._register_database()
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            future=True,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=True, bind=self.engine
        )
        self.session = self.get_session()
        self.auto_migrate = auto_migrate

        # Don't create tables here - let alembic handle it during migration

        # Handle legacy databases first
        if is_legacy_database(self.session):
            logger.info(
                "Legacy database detected - auto-stamping with appropriate revision"
            )
            stamped_revision = stamp_legacy_database(self.session, self.db_path)
            logger.info(f"Legacy database stamped with revision: {stamped_revision}")

        if auto_migrate and needs_migration(self.session):
            current_revision = get_database_revision(self.session)
            latest_revision = get_latest_revision()

            if is_database_newer_than_code(self.session):
                raise DatabaseVersionError(
                    f"Database has unknown revision '{current_revision}'. "
                    f"This database was likely created by a newer version of snkmt than this one (latest supported: {latest_revision}). "
                    f"Please upgrade snkmt or use a database created with a compatible version."
                )

            logger.info(
                f"Migrating database from {current_revision} to {latest_revision}"
            )

            # For new databases (no alembic_version), don't create backup
            create_backup = current_revision is not None
            self.migrate(create_backup=create_backup)
        elif not auto_migrate and needs_migration(self.session):
            if not ignore_version:
                current_revision = get_database_revision(self.session)
                latest_revision = get_latest_revision()
                raise DatabaseVersionError(
                    f"Database revision {current_revision} needs migration to {latest_revision} but auto_migrate is disabled. Please use snkmt db migrate command."
                )

    def migrate(
        self,
        desired_revision: Optional[str] = None,
        create_backup: bool = True,
    ) -> None:
        """
        Migrate database to desired revision.

        Parameters
        ----------
        desired_revision: Optional[str]
            Desired alembic revision to migrate to. If None, migrate to latest (head).
        create_backup: bool
            Create a timestamped backup of the database before migration.
        """
        assert self.engine
        assert self.session

        # Determine target revision
        if desired_revision is None:
            desired_revision = get_latest_revision()

        # Check current revision
        current_revision = get_database_revision(self.session)

        # Early exit if already at desired revision
        if current_revision == desired_revision:
            logger.info(
                f"Already at desired revision {current_revision}. No migrations performed."
            )
            return

        # Create backup if needed (skip for new databases)
        if create_backup and current_revision is not None:
            backup_path = self._create_backup()
            logger.info(f"Created database backup: {backup_path}")

        # Set up paths for alembic command
        db_dir = Path(__file__).parent
        alembic_config_file = db_dir / "alembic.ini"
        alembic_script_location = db_dir / "alembic"

        # Log migration details for debugging
        versions_dir = alembic_script_location / "versions"
        logger.info(f"Using alembic config file: {alembic_config_file}")
        logger.info(f"Looking for migration files in: {versions_dir}")
        logger.info(f"Migration files found: {list(versions_dir.glob('*.py'))}")

        # Create temporary config file with correct database URL
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ini", delete=False
        ) as temp_config:
            # Read original config and modify the database URL
            with open(alembic_config_file, "r") as original_config:
                config_content = original_config.read()

            # Replace the sqlalchemy.url line
            lines = config_content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("sqlalchemy.url"):
                    lines[i] = f"sqlalchemy.url = sqlite:///{self.db_path}"
                    break

            temp_config.write("\n".join(lines))
            temp_config_path = temp_config.name

        try:
            logger.info(
                f"Migrating db {self.db_path} from revision {current_revision} to {desired_revision}..."
            )

            # Run alembic upgrade using subprocess to avoid logging configuration conflicts

            cmd = [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                temp_config_path,
                "--raiseerr",
                "upgrade",
                desired_revision,
            ]
            logger.debug(f"Migration cmd: {cmd}")
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(db_dir), check=True
            )

            logger.info("Migration complete.")
            logger.debug(f"Migration stderr: {result.stderr}")
            logger.debug(f"Migration stdout: {result.stdout}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Migration failed with exit code {e.returncode}")
            logger.error(f"Stdout: {e.stdout}")
            logger.error(f"Stderr: {e.stderr}")
            raise DatabaseVersionError(
                f"Migration failed: {e.stderr or e.stdout}"
            ) from e
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise DatabaseVersionError(f"Migration failed: {e}") from e
        finally:
            # Clean up temporary config file
            try:
                os.unlink(temp_config_path)
            except OSError:
                pass

    def _register_database(self):
        """Register this database in the configuration."""
        try:
            from snkmt.core.config import DatabaseConfig

            config = DatabaseConfig()

            if config.get_database(self.db_file):
                return

            # Use file mtime as updated_at for existing databases
            if self.db_file.exists():
                updated_at = datetime.fromtimestamp(self.db_file.stat().st_mtime)
            else:
                updated_at = None  # Will use current time in dataclass

            config.add_database(
                path=self.db_file,
                display_name=None,  # Will default to path stem
            )

            # Update with mtime if it was an existing file
            if updated_at:
                # Re-read and update with mtime
                db_entry = config.get_database(self.db_file)
                if db_entry:
                    db_entry.updated_at = updated_at

                    config_data = config._load_config()
                    for db_data in config_data["databases"]:
                        if Path(db_data["path"]).resolve() == self.db_file.resolve():
                            db_data["updated_at"] = updated_at.isoformat()
                            break
                    config._save_config(config_data)

        except Exception as e:
            logger.debug(f"Failed to register database in config: {e}")

    def _create_backup(self) -> str:
        """Create a timestamped backup of the database file."""
        db_path = Path(self.db_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_revision = get_database_revision(self.session) or "new"
        backup_name = (
            f"{db_path.stem}_backup_{timestamp}_{current_revision}{db_path.suffix}"
        )
        backup_path = db_path.parent / backup_name

        # Close session temporarily to ensure file is not locked
        self.session.close()

        try:
            shutil.copy2(self.db_path, backup_path)
        finally:
            # Reopen session
            self.session = self.get_session()

        return str(backup_path)

    def get_revision(self) -> Optional[str]:
        """Get the current database revision."""
        return get_database_revision(self.session)

    def get_session(self) -> Session:
        """New SQLAlchemy session."""
        return self.SessionLocal()

    def get_db_info(self) -> dict:
        """Path, tables, and engine URL."""
        inspector = inspect(self.engine)
        return {
            "db_path": self.db_path,
            "tables": inspector.get_table_names(),
            "engine": str(self.engine.url),
            "schema_revision": self.get_revision(),
        }

    def close(self):
        """Close the database session and dispose of the engine."""
        if self.session:
            self.session.close()
        if self.engine:
            self.engine.dispose()


class AsyncDatabase:
    """Async connector for the snkmt DB"""

    def __init__(
        self,
        db_path: Optional[str] = None,
        create_db: bool = True,
        ignore_version: bool = False,
    ):
        # Use sync Database for all initialization and migration
        # TODO get rid of this and figure out how to properly do migrations with async engine (if its even different?)
        self._sync_db = Database(
            db_path=db_path,
            create_db=create_db,
            auto_migrate=True,  # Let sync db handle auto-migration
            ignore_version=ignore_version,
        )

        # Create async engine pointing to the same database file
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self._sync_db.db_path}",
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )

        self.SessionLocal = async_sessionmaker(
            autocommit=False, autoflush=True, bind=self.engine, class_=AsyncSession
        )

    # Delegate all sync operations to the sync database
    def migrate(self, **kwargs):
        """Migrate database to desired revision."""
        return self._sync_db.migrate(**kwargs)

    def get_revision(self) -> Optional[str]:
        """Get the current database revision."""
        return self._sync_db.get_revision()

    @property
    def db_path(self) -> str:
        """Get database path."""
        return self._sync_db.db_path

    def get_db_info(self) -> dict:
        """Path, tables, and engine URL (with async engine info)."""
        info = self._sync_db.get_db_info()
        # Update engine info to show async engine
        info["engine"] = str(self.engine.url)
        return info

    # Async-specific methods
    def get_session(self) -> async_sessionmaker[AsyncSession]:
        """Return async session factory."""
        return self.SessionLocal

    def get_workflow_repository(self) -> SQLAlchemyWorkflowRepository:
        return SQLAlchemyWorkflowRepository(self.get_session())

    async def close(self):
        """Close both async and sync engines."""
        await self.engine.dispose()
        self._sync_db.close()
