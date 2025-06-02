import typer
from typing import Optional
from snkmt.db.session import Database

app = typer.Typer(
    name="snkmt",
    help="Monitor Snakemake workflow executions.",
    add_completion=False,
    no_args_is_help=True,
)

db_app = typer.Typer()
app.add_typer(db_app, name="db")


### MAIN APP COMMANDS
@app.callback()
def callback():
    pass


@app.command("console")
def launch_console(
    directory: Optional[str] = typer.Option(
        None, "--db-path", "-d", help="Path to the database."
    ),
):
    """Launch the interactive console UI"""
    from snkmt.console.app import run_app

    db = Database(db_path=directory).get_session()
    run_app(db)


#### DB APP COMMANDS
@db_app.callback()
def db_callback():
    pass


@db_app.command("info")
def db_info(db: Optional[str]):
    database = Database(db, create_db=False, auto_migrate=False)
    print(f"Database info: {database.get_db_info()}")


@db_app.command("migrate")
def db_migrate(db: Optional[str]):
    database = Database(db, create_db=False, auto_migrate=False, ignore_version=True)
    database.migrate()


def main():
    app()
