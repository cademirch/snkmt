from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Container
from textual import events
from typing import Optional
from sqlalchemy.orm import Session
from snkmt.console.screens import WorkflowSummaryScreen


class snkmtApp(App):
    """A Textual app for monitoring and analyzing Snakemake workflows."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        width: 100%;
        height: 100%;
    }

    .welcome {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
    }

    DataTable {
        .datatable--cursor {
            background: transparent;
            text-style: none;
        }
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("?", "toggle_help", "Help"),
    ]

    def __init__(self, db_session: Session):
        super().__init__()
        self.db_session = db_session

    def compose(self) -> ComposeResult:
        yield Header(
            show_clock=True,
        )
        with Container(id="main-container"):
            yield Static(
                "Welcome to snkmt!\n\nSelect a workflow to view details.",
                classes="welcome",
            )

        yield Footer()

    def action_toggle_help(self) -> None:
        """Toggle help screen."""
        self.bell()  # Just a placeholder for now

    def on_mount(self) -> None:
        self.title = "snkmt console"
        self.push_screen(WorkflowSummaryScreen(self.db_session))


def run_app(db_session: Session):
    """Run the Textual app."""
    app = snkmtApp(db_session)
    app.run()
