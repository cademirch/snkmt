from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
from snkmt.core.db import SNKMT_DIR


@dataclass
class Database:
    """Represents a database configuration."""

    path: Path
    display_name: Optional[str] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        # Ensure path is absolute and resolved
        if isinstance(self.path, str):
            self.path = Path(self.path)
        self.path = self.path.resolve()

        if self.display_name is None:
            self.display_name = self.path.stem
        if self.updated_at is None:
            self.updated_at = datetime.now()

    @property
    def exists(self) -> bool:
        """Check if the database file exists."""
        return self.path.exists()

    @property
    def connection_string(self) -> str:
        """Return SQLite connection string for async usage."""
        return f"sqlite+aiosqlite:///{self.path}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["path"] = str(self.path)  # Convert Path to string for JSON
        if self.updated_at:
            data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Database":
        """Create Database from dictionary."""
        if "updated_at" in data and data["updated_at"]:
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        data["path"] = Path(data["path"])  # Convert string back to Path
        return cls(**data)


class DatabaseConfig:
    """Manages database configuration."""

    def __init__(self):
        self.config_file = SNKMT_DIR / "databases.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Ensure config directory exists."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return {"databases": []}

        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"databases": []}

    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file."""
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def list_databases(self) -> List[Database]:
        """List all configured databases."""
        config = self._load_config()
        return [Database.from_dict(db_data) for db_data in config.get("databases", [])]

    def add_database(self, path: Path, display_name: Optional[str] = None) -> Database:
        """Add a new database. Path is the unique identifier."""
        # Check if path already exists
        existing = self.get_database(path)
        if existing:
            raise ValueError(f"Database at path '{path}' already exists")

        database = Database(path=path, display_name=display_name)

        config = self._load_config()
        config["databases"].append(database.to_dict())
        self._save_config(config)

        return database

    def remove_database(self, path: Path) -> bool:
        """Remove a database by path. Returns True if removed."""
        config = self._load_config()
        databases = config["databases"]

        for i, db_data in enumerate(databases):
            if Path(db_data["path"]).resolve() == path.resolve():
                del databases[i]
                self._save_config(config)
                return True

        return False

    def get_database(self, path: Path) -> Optional[Database]:
        """Get a database by path."""
        for database in self.list_databases():
            if database.path.resolve() == path.resolve():
                return database
        return None
