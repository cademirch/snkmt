from textual import events
from rich.text import Text
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, Input, Static
from textual.screen import Screen
from textual.app import App, ComposeResult
from textual.containers import Container
from uuid import UUID
from snkmt.console.widgets import Table
from sqlalchemy.orm import Session
from snkmt.db.models import Workflow


class WorkflowDetailScreen(Screen):
    """
    For now this just shows rule statuses for a workflow. Selecting a rule will then show all jobs for a rule.
    In the future this could show more info about the workflow at the top and then table of rules.
    Maybe tabs for rules/jobs? Progress bar, etc
    """

    def __init__(self, db_session: Session, workflow_id: UUID, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_id = workflow_id
        self.db_session = db_session
        self.table = Table()
        self.table.cursor_type = "row"
        self.table.add_columns(
            "Rule",
            "Progress",
        )

    def compose(self) -> ComposeResult:
        """Create child widgets for the main screen."""
        self.table.focus()
        yield Container(Header(show_clock=True), self.table, Footer())

    def on_mount(self) -> None:
        """Load data when the screen is mounted."""
        self.load_workflow_data()

    def load_workflow_data(self) -> None:
        """Load workflow data from the database and populate the table."""
        # Clear existing rows
        self.table.clear()
        workflow = self.db_session.query(Workflow).get(self.workflow_id)
        if workflow:
            for rule in workflow.rules:
                rule_name = rule.name
                progress = (
                    format(rule.progress, ".2%") if rule.progress is not None else "N/A"
                )
                self.table.add_row(rule_name, progress, key=rule_name)


class WorkflowSummaryScreen(Screen):
    """
    Shows table of workflows in database
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, db_session: Session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_session = db_session
        self.table = Table()
        self.table.cursor_type = "row"
        self.table.cursor_foreground_priority = "renderable"
        self.table.add_columns("UUID", "Status", "Snakefile", "Started At", "Progress")

    def compose(self) -> ComposeResult:
        """Create child widgets for the main screen."""
        self.table.focus()
        yield Container(Header(show_clock=True), self.table, Footer())

    def on_mount(self) -> None:
        """Load data when the screen is mounted."""
        self.load_workflow_data()

    def load_workflow_data(self) -> None:
        """Load workflow data from the database and populate the table."""
        # Clear existing rows
        self.table.clear()

        # Get workflows from the database
        workflows = Workflow.list_all(self.db_session, limit=100)

        # Add rows to the table
        for workflow in workflows:
            uuid_str = str(workflow.id)
            status = workflow.status.value if workflow.status else "UNKNOWN"
            snakefile = "N/A"
            if workflow.snakefile:
                snakefile = Text(workflow.snakefile, overflow="ellipsis")

            snakefile = workflow.snakefile or "N/A"
            started_at = (
                workflow.started_at.strftime("%Y-%m-%d %H:%M:%S")
                if workflow.started_at
                else "N/A"
            )
            progress = f"[green]{format(workflow.progress, '.2%')}[/green]"

            self.table.add_row(
                uuid_str[-6:], status, snakefile, started_at, progress, key=uuid_str
            )

    def on_data_table_row_selected(self, event: Table.RowSelected) -> None:
        """Handle row selection event."""

        workflow_id = UUID(event.row_key.value)

        self.log.warning(f"Selected workflow: {workflow_id}")
        self.app.push_screen(WorkflowDetailScreen(self.db_session, workflow_id))
