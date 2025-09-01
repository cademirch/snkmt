import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from platformdirs import user_data_dir
from loguru import logger
from snkmt.core.models.version import DBVersion
from snkmt.core.db.version import (
    DB_VERSIONS,
    DB_MAX_VERSION,
    DB_MIN_VERSION,
    DBVersionError,
    null_db_version,
)
from snkmt.core.models.base import Base
from alembic.command import downgrade, upgrade
from alembic.config import Config as AlembicConfig


SNKMT_DIR = Path(user_data_dir(appname="snkmt", appauthor=False, ensure_exists=True))


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
            db_file = Path(db_path)

        else:
            db_file = default_db_path

        if not db_file.parent.exists():
            if create_db:
                db_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                raise DatabaseNotFoundError(f"No DB directory: {db_file.parent}")

        if not db_file.exists() and not create_db:
            raise DatabaseNotFoundError(f"DB file not found: {db_file}")

        self.db_path = str(db_file)
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

        Base.metadata.create_all(bind=self.engine)

        current_version = self.get_version()
        latest_version = DB_MAX_VERSION

        if current_version == null_db_version:
            self.migrate(create_backup=False)
        elif current_version < latest_version:
            if auto_migrate:
                self.migrate()
            else:
                if not ignore_version:
                    raise DBVersionError(
                        f"Database version {current_version} needs migration but auto_migrate is disabled Please use snkmt db migrate command."
                    )

    def migrate(
        self,
        desired_version: Optional[DBVersion] = None,
        upgrade_only: bool = False,
        create_backup: bool = True,
    ) -> None:
        """
        Migrate database to desired version.

        Parameters
        ----------
        desired_version: Optional[DBVersionInfo]
            Desired version to update redun database to. If null, update to latest version.
        upgrade_only: bool
            By default, this function will perform both upgrades and downgrades.
            Set this to true to prevent downgrades (such as during automigration).
        create_backup: bool
            Create a timestamped backup of the database before migration.
        """
        assert self.engine
        assert self.session

        # Determine target version
        _, newest_allowed_version = DB_MIN_VERSION, DB_MAX_VERSION
        if desired_version is None:
            desired_version = newest_allowed_version

        # Check current version
        current_version = self.get_version()

        # Early exit if already at desired version
        if current_version == desired_version:
            logger.info(
                f"Already at desired db version {current_version}. No migrations performed."
            )
            return

        # Validate version compatibility
        if current_version > newest_allowed_version:
            raise DBVersionError(
                f"Database is too new for this program: {current_version} > {newest_allowed_version}"
            )

        # Handle downgrade restrictions
        if current_version > desired_version and upgrade_only:
            logger.info(
                f"Already at db version {current_version}, upgrade_only is set."
            )
            return

        # Create backup if needed
        if create_backup and current_version != null_db_version:
            backup_path = self._create_backup()
            logger.info(f"Created database backup: {backup_path}")

        # Set up Alembic configuration
        db_dir = Path(__file__).parent
        alembic_config_file = db_dir / "alembic.ini"
        alembic_script_location = db_dir / "alembic"

        config = AlembicConfig(alembic_config_file)
        config.set_main_option("script_location", str(alembic_script_location))
        config.session = self.session  # type: ignore

        # Log migration files for debugging
        versions_dir = alembic_script_location / "versions"
        logger.info(f"Using alembic config file: {alembic_config_file}")
        logger.info(f"Looking for migration files in: {versions_dir}")
        logger.info(f"Migration files found: {list(versions_dir.glob('*.py'))}")

        # Perform the migration
        try:
            if desired_version > current_version:
                # Upgrade
                logger.info(
                    f"Upgrading db from version {current_version} to {desired_version}..."
                )
                upgrade(config, desired_version.id)
                logger.info("Upgrade complete.")
            else:
                # Downgrade
                logger.info(
                    f"Downgrading db from version {current_version} to {desired_version}..."
                )
                downgrade(config, desired_version.id)
                logger.info("Downgrade complete.")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            # Re-raise the exception without modifying the version record
            raise

        # Only update version record after successful migration
        try:
            # Remove old version record(s)
            self.session.query(DBVersion).delete()

            # Add new version record
            self.session.add(
                DBVersion(
                    id=desired_version.id,
                    major=desired_version.major,
                    minor=desired_version.minor,
                )
            )

            # Commit the version update
            self.session.commit()
            logger.info(f"Database version updated to {desired_version}")

        except Exception as e:
            # If version update fails, rollback and provide context
            self.session.rollback()
            logger.error(f"Failed to update version record after migration: {e}")
            raise DBVersionError(
                f"Migration succeeded but failed to update version record. "
                f"Database schema is at {desired_version} but version record may show {current_version}. "
                f"Error: {e}"
            )

    def _create_backup(self) -> str:
        """Create a timestamped backup of the database file."""
        db_path = Path(self.db_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_version_id = self.get_version().id
        backup_name = (
            f"{db_path.stem}_backup_{timestamp}_{current_version_id}_{db_path.suffix}"
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

    def get_version(self) -> DBVersion:
        """Get the current database version."""
        assert self.session
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()

        if DBVersion.__tablename__ in table_names:
            version_row = (
                self.session.query(DBVersion).order_by(DBVersion.major.desc()).first()
            )
            if version_row:
                return version_row

        return null_db_version

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
            "schema_revision": self.get_version().id,
        }

    def close(self):
        """Close the database session and dispose of the engine."""
        if self.session:
            self.session.close()
        if self.engine:
            self.engine.dispose()


class AsyncDatabase:
    """Async connector for the Snakemake SQLite DB."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        create_db: bool = True,
        ignore_version: bool = False,
    ):
        default_db_path = SNKMT_DIR / "snkmt.db"

        if db_path:
            db_file = Path(db_path)
        else:
            db_file = default_db_path

        if not db_file.parent.exists():
            if create_db:
                db_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                raise DatabaseNotFoundError(f"No DB directory: {db_file.parent}")

        if not db_file.exists() and not create_db:
            raise DatabaseNotFoundError(f"DB file not found: {db_file}")

        self.db_path = str(db_file)

        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.db_path}",
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )

        self.SessionLocal = async_sessionmaker(
            autocommit=False, autoflush=True, bind=self.engine, class_=AsyncSession
        )

        self.ignore_version = ignore_version

    async def initialize(self):
        """Async initialization - must be called after __init__."""
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        current_version = await self.get_version()
        latest_version = self.get_all_versions()[-1]

        if current_version == null_db_version:
            # For new databases, run sync migration
            await self._run_sync_migration(create_backup=False)
        elif current_version < latest_version:
            raise DBVersionError(
                f"Current DB version: {current_version} is incompatible with latest: {latest_version}."
                "Auto-migration not supported in async. "
                "Please use snkmt db migrate command."
            )

    async def _run_sync_migration(self, create_backup: bool = True):
        """Run synchronous migration in async context."""

        sync_db = Database(
            db_path=self.db_path,
            create_db=False,
            auto_migrate=False,
            ignore_version=True,
        )
        try:
            sync_db.migrate(create_backup=create_backup)
        finally:
            sync_db.close()

    async def get_version(self) -> DBVersion:
        """Get the current database version."""
        async with self.engine.begin() as conn:

            def check_tables(connection):
                inspector = inspect(connection)
                return DBVersion.__tablename__ in inspector.get_table_names()

            has_table = await conn.run_sync(check_tables)

        if not has_table:
            return null_db_version

        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBVersion).order_by(DBVersion.major.desc())
            )
            version_row = result.scalar_one_or_none()
            if version_row:
                return version_row

        return null_db_version

    @staticmethod
    def get_all_versions() -> List[DBVersion]:
        return DB_VERSIONS

    @staticmethod
    def get_db_version_required() -> Tuple[DBVersion, DBVersion]:
        """Returns the DB version range required by this library."""
        return DB_MIN_VERSION, DB_MAX_VERSION

    def get_session(self) -> async_sessionmaker[AsyncSession]:
        """Return async session factory."""
        return self.SessionLocal

    async def get_db_info(self) -> dict:
        """Path, tables, and engine URL."""
        async with self.engine.begin() as conn:

            def get_info(connection):
                inspector = inspect(connection)
                return inspector.get_table_names()

            tables = await conn.run_sync(get_info)

        current_version = await self.get_version()

        return {
            "db_path": self.db_path,
            "tables": tables,
            "engine": str(self.engine.url),
            "schema_revision": current_version.id,
        }

    async def close(self):
        """Close the async engine."""
        await self.engine.dispose()
