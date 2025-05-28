import os  # Add this import
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session


class DatabaseNotFoundError(Exception):
    """Raised when the Snakemake DB file isn’t found and creation is disabled."""

    pass


class Database:
    """Simple connector for the Snakemake SQLite DB."""

    def __init__(self, db_path: Optional[str] = None, create_db: bool = True):
        env_db_path = os.getenv("SNKMT_DB_PATH")
        default_db_path = Path.home() / ".snkmt" / "snkmt.db"

        if db_path:
            db_file = Path(db_path)
        elif env_db_path:
            db_file = Path(env_db_path)
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
        }

    @classmethod
    def get_database(
        cls, db_path: Optional[str] = None, create_db: bool = True
    ) -> "Database":
        """Factory alias for the constructor."""
        return cls(db_path=db_path, create_db=create_db)
