import os
from pathlib import Path
from typing import Optional, List
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session


class DatabaseNotFoundError(Exception):
    """Exception raised when Snakemake database cannot be found."""

    pass


class Database:
    """Handles connecting to the Snakemake database."""

    def __init__(self, db_path: Optional[str] = None, directory: Optional[str] = None):
        """
        Initialize the database connection.

        Args:
            db_path: Direct path to the database file. If provided, this takes precedence.
            directory: Path to directory containing .snakemake folder or direct path
                      to .snakemake folder. Used only if db_path is None.
                      Default database location is ./.snakemake/log/snakemake.log.db

        Raises:
            DatabaseNotFoundError: If Snakemake database cannot be found when using directory.
        """
        if db_path is not None:
            self.db_path = db_path
        else:
            self.db_path = self._find_database(directory)

        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def _find_database(self, directory: Optional[str] = None) -> str:
        """
        Find the Snakemake database file.

        Args:
            directory: Path to search for the database. If None, uses current directory.
                       Can be path to .snakemake dir or its parent.
                       Default database location is ./.snakemake/log/snakemake.log.db

        Returns:
            str: Path to the Snakemake database file.

        Raises:
            DatabaseNotFoundError: If Snakemake database cannot be found.
        """
        if directory is None:
            directory = os.getcwd()

        directory_path = Path(directory).resolve()

        if directory_path.name == ".snakemake":
            snakemake_dir = directory_path
        else:
            snakemake_dir = directory_path / ".snakemake"

        default_db_path = snakemake_dir / "log" / "snakemake.log.db"
        if not default_db_path.parent.exists():
            os.makedirs(default_db_path.parent, exist_ok=True)

        possible_db_paths = [
            default_db_path,
            snakemake_dir / "snakemake.log.db",
        ]

        for db_path in possible_db_paths:
            if db_path.exists():
                return str(db_path)

        # If no database exists, return the default path (it will be created later)
        return str(default_db_path)

    def get_session(self) -> Session:
        """
        Create and return a new database session.

        Returns:
            Session: SQLAlchemy session connected to the Snakemake database.
        """
        return self.SessionLocal()

    def get_db_info(self) -> dict:
        """
        Get information about the connected database.

        Returns:
            dict: Information about the database including path and tables.
        """
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()

        return {
            "db_path": self.db_path,
            "tables": tables,
            "engine": str(self.engine.url),
        }

    @classmethod
    def get_database(
        cls, db_path: Optional[str] = None, directory: Optional[str] = None
    ) -> "Database":
        """
        Factory class method to get a database connection.

        Args:
            db_path: Direct path to the database file. If provided, this takes precedence.
            directory: Path to search for the database. Used only if db_path is None.
                       Default database location is ./.snakemake/log/snakemake.log.db

        Returns:
            Database: Initialized database connection.
        """
        return cls(db_path=db_path, directory=directory)