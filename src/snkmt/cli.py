import typer
import sys
from typing import Optional
from pathlib import Path
from loguru import logger
from snkmt.core.db.session import Database
from snkmt.core.config import DatabaseConfig
from beaupy import select_multiple, confirm
from rich.console import Console
from rich.table import Table


def verbose_callback(value: bool):
    """Configure logging based on verbose flag."""
    logger.remove()  # Remove all existing handlers first
    # see https://loguru.readthedocs.io/en/stable/resources/troubleshooting.html#how-do-i-fix-valueerror-i-o-operation-error-on-closed-file
    logger.add(
        lambda msg: sys.stderr.write(msg),  # type: ignore
        level="DEBUG" if value else "INFO",
    )
    return value


VerboseOption = typer.Option(
    False,
    "--verbose",
    "-v",
    help="Enable debug logging.",
    callback=verbose_callback,
    is_eager=True,
)


app = typer.Typer(
    name="snkmt",
    help="Monitor Snakemake workflow executions.",
    add_completion=False,
    no_args_is_help=True,
)

db_app = typer.Typer(
    name="db",
    help="Manage snkmt databases.",
    add_completion=False,
    no_args_is_help=True,
)
app.add_typer(db_app)

config_app = typer.Typer(
    name="config",
    help="Manage database configuration.",
    add_completion=False,
    no_args_is_help=True,
)
db_app.add_typer(
    config_app,
)


### MAIN APP COMMANDS
def version_callback(value: bool):
    if value:
        from snkmt.version import VERSION

        typer.echo(f"snkmt {VERSION}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    verbose: bool = VerboseOption,
):
    """Monitor Snakemake workflow executions."""
    pass


@app.command("console")
def launch_console(
    directory: Optional[list[str]] = typer.Option(
        None,
        "--db-path",
        "-d",
        help="Path to a snkmt database. Can be specified multiple times to monitor multiple databases.",
    ),
):
    """Launch the interactive console UI to monitor workflows."""
    from snkmt.console.app import run_app

    run_app(directory)


#### DB APP COMMANDS
@db_app.callback()
def db_callback():
    pass


@db_app.command("info")
def db_info(
    db: Optional[str] = typer.Option(
        None,
        "--db-path",
        "-d",
        help="Database path (default: user data dir).",
    ),
    verbose: bool = VerboseOption,
):
    """Display database information and schema version."""
    database = Database(db, create_db=False, auto_migrate=False)
    print(f"Database info: {database.get_db_info()}")


@db_app.command("migrate")
def db_migrate(
    db: Optional[str] = typer.Option(
        None,
        "--db-path",
        "-d",
        help="Database path (default: user data dir).",
    ),
    verbose: bool = VerboseOption,
):
    """Run database migrations to upgrade schema to latest version."""
    database = Database(db, create_db=False, auto_migrate=False, ignore_version=True)
    database.migrate()


@db_app.command("stamp")
def db_stamp(
    revision: Optional[str] = typer.Argument(
        None, help="Alembic revision to stamp (default: latest)."
    ),
    db: Optional[str] = typer.Option(
        None,
        "--db-path",
        "-d",
        help="Database path (default: user data dir).",
    ),
    verbose: bool = VerboseOption,
):
    """Manually stamp database with a schema revision without running migrations."""
    import subprocess
    import sys
    from pathlib import Path
    from platformdirs import user_data_dir
    from snkmt.core.db.version import get_latest_revision

    # Determine database path
    if db is None:
        db_path = Path(user_data_dir(appname="snkmt", appauthor=False)) / "snkmt.db"
    else:
        db_path = Path(db)

    if not db_path.exists():
        typer.echo(f"Error: Database file not found: {db_path}", err=True)
        raise typer.Exit(1)

    # Use latest revision if none specified
    if revision is None:
        revision = get_latest_revision()
        if revision is None:
            typer.echo("Error: No migrations found", err=True)
            raise typer.Exit(1)
        typer.echo(f"Using latest revision: {revision}")

    # Setup paths for alembic command
    db_dir = Path(__file__).parent / "core/db"
    alembic_config_file = db_dir / "alembic.ini"

    # Create temporary config file with correct database URL
    import tempfile

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
                lines[i] = f"sqlalchemy.url = sqlite:///{db_path}"
                break

        temp_config.write("\n".join(lines))
        temp_config_path = temp_config.name

    try:
        # Run alembic stamp using subprocess to avoid logging configuration conflicts
        cmd = [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            temp_config_path,
            "--raiseerr",
            "stamp",
            revision,
        ]

        subprocess.run(cmd, capture_output=True, text=True, cwd=str(db_dir), check=True)

        typer.echo(f"Database stamped with revision: {revision}")
    except subprocess.CalledProcessError as e:
        typer.echo(
            f"Error stamping database (exit code {e.returncode}): {e.stderr or e.stdout}",
            err=True,
        )
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error stamping database: {e}", err=True)
        raise typer.Exit(1)
    finally:
        # Clean up temporary config file
        try:
            import os

            os.unlink(temp_config_path)
        except OSError:
            pass


#### CONFIG APP COMMANDS
@config_app.callback()
def config_callback(verbose: bool = VerboseOption):
    pass


@config_app.command("list")
def config_list():
    """List all configured databases."""
    config = DatabaseConfig()
    databases = config.list_databases()

    if not databases:
        typer.echo("No databases configured.")
        return

    console = Console()
    table = Table(
        title=str(config.config_file),
        show_header=True,
        show_lines=False,
        show_edge=False,
        box=None,
        header_style=None,
    )
    table.add_column("name", justify="right")
    table.add_column("path")
    table.add_column("exists", justify="right")

    for db in databases:
        status = "✓" if db.exists else "✗"
        table.add_row(db.display_name, str(db.path), status)

    console.print(table)


@config_app.command("add")
def config_add(
    path: str = typer.Argument(help="Path to the database file to add."),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Display name for the database (default: filename stem).",
    ),
):
    """Add a database to the configuration file."""
    db_path = Path(path).resolve()

    if not db_path.exists():
        typer.echo(f"Warning: Database file does not exist: {db_path}")
        if not confirm("Add anyway?"):
            raise typer.Exit(1)

    if name is None:
        name = db_path.stem

    config = DatabaseConfig()
    try:
        config.add_database(db_path, name)
        typer.echo(f"Added database: {name} -> {db_path}")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@config_app.command("remove")
def config_remove():
    """Interactively remove databases from the configuration file."""
    config = DatabaseConfig()
    databases = config.list_databases()

    if not databases:
        typer.echo("No databases configured.")
        return

    options = [f"{db.display_name} ({db.path})" for db in databases]

    selected = select_multiple(options, minimal_count=1, return_indices=True)  # type: ignore

    if not selected:
        typer.echo("No databases selected.")
        return

    for idx in selected:
        db = databases[idx]
        if config.remove_database(db.path):
            typer.echo(f"Removed: {db.display_name}")
        else:
            typer.echo(f"Failed to remove: {db.display_name}")


@config_app.command("discover")
def config_discover(
    directory: Optional[str] = typer.Argument(
        None, help="Directory to search for .db files (default: current directory)."
    ),
):
    """Search for database files recursively and add them to configuration."""
    search_dir = Path(directory) if directory else Path.cwd()

    if not search_dir.exists():
        typer.echo(f"Error: Directory not found: {search_dir}", err=True)
        raise typer.Exit(1)

    # Find .db files
    db_files = list(search_dir.rglob("*.db"))

    if not db_files:
        typer.echo(f"No .db files found in {search_dir}")
        return

    typer.echo(f"Found {len(db_files)} database files:")
    config = DatabaseConfig()

    # Filter out already configured databases
    new_files = []
    for db_file in db_files:
        existing = config.get_database(db_file)
        if existing:
            typer.echo(f"  {db_file} (already configured)")
        else:
            new_files.append(db_file)
            typer.echo(f"  {db_file}")

    if not new_files:
        typer.echo("All found databases are already configured.")
        return

    options = [str(db_file) for db_file in new_files]
    selected = select_multiple(options, return_indices=True)  # type: ignore

    if not selected:
        typer.echo("No databases selected to add.")
        return

    for idx in selected:
        db_file = new_files[idx]
        try:
            config.add_database(db_file, db_file.stem)
            typer.echo(f"Added: {db_file.stem}")
        except ValueError as e:
            typer.echo(f"Error adding {db_file}: {e}")


def main():
    app()
