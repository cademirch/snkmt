import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from platformdirs import user_data_dir
from loguru import logger
from snkmt.db.models.version import (
    DB_VERSIONS,
    DB_MAX_VERSION,
    DB_MIN_VERSION,
    DBVersion,
    DBVersionError,
    null_db_version,
)
from snkmt.db.models.base import Base
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
        logfile = db_file.parent / "snkmt.log"
        logger.add(logfile)
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
        latest_version = self.get_all_versions()[-1]

        if current_version == null_db_version:
            self.session.add(
                DBVersion(
                    id=latest_version.id,
                    major=latest_version.major,
                    minor=latest_version.minor,
                )
            )
            self.session.commit()
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
        _, newest_allowed_version = self.get_db_version_required()

        if desired_version is None:
            desired_version = newest_allowed_version

        version = self.get_version()

        if version == desired_version:
            logger.info(
                f"Already at desired db version {version}. No migrations performed."
            )
            return

        if version > newest_allowed_version:
            # db version is too new to work with, abort.
            raise DBVersionError(
                f"Database is too new for this program: {version} > {newest_allowed_version}"
            )

        # Create backup before migration if requested and not a new database
        if create_backup and version != null_db_version:
            backup_path = self._create_backup()
            logger.info(f"Created database backup: {backup_path}")

        db_dir = Path(__file__).parent
        alembic_config_file = db_dir / "alembic.ini"
        alembic_script_location = db_dir / "alembic"

        config = AlembicConfig(alembic_config_file)
        config.set_main_option("script_location", str(alembic_script_location))
        config.session = self.session  # type: ignore

        # Perform migration.
        if desired_version > version:
            logger.info(f"Upgrading db from version {version} to {desired_version}...")
            upgrade(config, desired_version.id)
        elif desired_version < version and not upgrade_only:
            logger.info(
                f"Downgrading db from version {version} to {desired_version}..."
            )
            downgrade(config, desired_version.id)
        else:
            # Already at desired version.
            logger.info(f"Already at desired db version {version}.")
            return

        # Record migration has been applied.
        self.session.add(
            DBVersion(
                id=desired_version.id,
                major=desired_version.major,
                minor=desired_version.minor,
            )
        )

        # Commit migrations. This also ensures there are no checkedout connections.
        self.session.commit()

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

    @staticmethod
    def get_all_versions() -> List[DBVersion]:
        return DB_VERSIONS

    @staticmethod
    def get_db_version_required() -> Tuple[DBVersion, DBVersion]:
        """
        Returns the DB version range required by this library.
        """
        return DB_MIN_VERSION, DB_MAX_VERSION

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
