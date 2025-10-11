import pytest
from pathlib import Path
from typer.testing import CliRunner
from snkmt.cli import app
from snkmt.core.db.session import Database
import tempfile


runner = CliRunner()


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / "test.db"


@pytest.fixture
def temp_db(temp_db_path):
    """Create a temporary database."""
    db = Database(db_path=str(temp_db_path), create_db=True)
    db.close()
    return temp_db_path


def test_cli_version():
    """Test that --version flag shows version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "snkmt" in result.stdout


def test_db_info_command(temp_db):
    """Test db info command on a new database."""
    result = runner.invoke(app, ["db", "info", "--db-path", str(temp_db)])
    assert result.exit_code == 0
    assert "Database info:" in result.stdout


def test_db_migrate_command(temp_db):
    """Test db migrate command."""
    result = runner.invoke(app, ["db", "migrate", "--db-path", str(temp_db)])
    assert result.exit_code == 0


def test_verbose_flag_enables_debug_logging(temp_db):
    """Test that verbose flag enables DEBUG level logging."""
    
    result = runner.invoke(app, ["db", "migrate", "-v","--db-path", str(temp_db)])
    assert result.exit_code == 0

    
    assert "DEBUG" in result.stderr


def test_verbose_flag_disabled_by_default(temp_db):
    """Test that default logging level is INFO (not DEBUG)."""
    
    result = runner.invoke(app, ["db", "migrate", "--db-path", str(temp_db)])
    assert result.exit_code == 0

    assert not "DEBUG" in result.stderr
