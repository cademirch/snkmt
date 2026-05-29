from pathlib import Path
from textual.app import App, ComposeResult
from textual.command import CommandPalette
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Label,
    ListView,
)
from typing import Optional
from textual.screen import Screen
from textual.containers import Horizontal, Container
from textual.css.query import NoMatches
from textual import on

from snkmt.version import VERSION
from snkmt.console.command import SelectDatabaseCommand, DatabaseSourceProvider
from snkmt.console.views.overview import WorkflowListView
from snkmt.console.widgets import LogFileModal
from snkmt.core.db.session import AsyncDatabase


class AppHeader(Horizontal):
    """The header of the app."""

    def __init__(
        self,
        *children: Widget,
        datasource: str | None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        markup: bool = True,
    ) -> None:
        self.datasource = datasource
        super().__init__(
            *children,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            markup=markup,
        )

    def compose(self) -> ComposeResult:
        yield Label(f"[b]snkmt[/] [dim]{VERSION}[/]", id="app-title")
        if not self.datasource:
            yield Label("No database selected", id="app-db-path")
        else:
            yield Label(f"Connected to: {self.datasource}", id="app-db-path")


class DashboardScreen(Screen):
    COMMANDS = {SelectDatabaseCommand}
    BINDINGS = [
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_previous", "Previous"),
        ("r", "force_refresh", "Refresh"),
    ]

    def __init__(self, datasource_url: Optional[str] = None) -> None:
        super().__init__()
        self.datasource = datasource_url

    def action_force_refresh(self) -> None:
        try:
            self.query_one(WorkflowListView).force_refresh()
        except NoMatches:
            pass

    def action_select_database_source(self) -> None:
        self.app.push_screen(
            CommandPalette(
                providers=[DatabaseSourceProvider],
                placeholder="Search for database sources…",
            )
        )

    def compose(self) -> ComposeResult:
        try:
            db = AsyncDatabase(self.datasource, create_db=False)
            repo = db.get_workflow_repository()
            yield AppHeader(datasource=db.db_path, id="header")
            yield WorkflowListView(repo)
        except Exception as e:
            from snkmt.core.db.session import DatabaseNotFoundError

            error_container = Container(classes="section", id="error-container")
            error_container.border_title = "Database Connection Error"
            with error_container:
                if isinstance(e, DatabaseNotFoundError):
                    error_type = "Database Not Found"
                    error_details = str(e)
                    suggestion = (
                        "\n Try selecting a different database source with Ctrl+P"
                    )
                else:
                    error_type = f"{type(e).__name__}"
                    error_details = str(e)
                    suggestion = "\n Check the database path and permissions"
                yield Label(
                    f"{error_type}\n\nDatasource: {self.datasource}\n\n"
                    f"Details:\n{error_details}{suggestion}",
                    id="error-message",
                    classes="error-text",
                )
        yield Footer(id="footer")

    @on(WorkflowListView.WorkflowSelected)
    def handle_workflow_selected(
        self, message: WorkflowListView.WorkflowSelected
    ) -> None:
        from snkmt.console.views.detail import WorkflowDetailScreen

        try:
            db = AsyncDatabase(self.datasource, create_db=False)
            repo = db.get_workflow_repository()
            self.app.push_screen(
                WorkflowDetailScreen(repo, message.workflow_id, self.datasource)
            )
        except Exception as e:
            self.app.notify(f"Could not open workflow: {e}", severity="error")


class snkmtApp(App):
    """A Textual app for monitoring Snakemake workflows."""

    CSS_PATH = "snkmt.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_previous", "Previous"),
    ]

    def __init__(self, refresh_interval: float, databases: Optional[list[str]] = None):
        super().__init__()
        self.refresh_interval = refresh_interval
        self.databases = databases
        if self.databases is None:
            self.current_source = None  # just use default snkmt db. should probably make this more explicit
        else:
            self.current_source = self.databases[0]

    def set_database_source(self, source: str) -> None:
        """Set the database source."""
        self.current_source = source
        self.notify(f"Connected to: {source}", severity="information")
        self.switch_screen(DashboardScreen(source))

    def on_ready(self) -> None:
        self.title = "snkmt console"
        self.theme = "gruvbox"
        self.push_screen(DashboardScreen(self.current_source))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.log.debug(f"List view selected {event.list_view=} {event.item=}")

        if event.item.name:
            self.log.debug(f"log file selected: {event.item.name}")
            self.push_screen(LogFileModal(Path(event.item.name)))

    def action_focus_next(self) -> None:
        """Focus the next widget."""
        self.screen.focus_next()

    def action_focus_previous(self) -> None:
        """Focus the previous widget."""
        self.screen.focus_previous()


def run_app(refresh_interval: float, databases: Optional[list[str]] = None) -> None:
    """Run the Textual app."""
    app = snkmtApp(refresh_interval, databases)
    app.run()
