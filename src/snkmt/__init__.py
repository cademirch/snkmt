import typer
from typing import Optional
from snkmt.db.session import Database

app = typer.Typer(
    name="snkmt",
    help="Monitor Snakemake workflow executions.",
    add_completion=False,
    no_args_is_help=True,
)


@app.callback()
def callback():
    pass


@app.command("ls")
def list_workflows(
    directory: str = typer.Option(
        None, "--directory", "-d", help="Path to the workflow directory"
    ),
    limit: int = typer.Option(4, "--limit", "-n", help="Number of workflows to show"),
):
    """List workflows in database"""
    pass


@app.command("console")
def launch_console(
    workflow_id: Optional[int] = typer.Argument(
        None, help="Workflow ID to view (if not provided, shows workflow selection)"
    ),
):
    """Launch the interactive console UI"""
    from snkmt.console.app import run_app

    db = Database.get_database(create_db=False).get_session()
    run_app(db)


def main():
    app()
