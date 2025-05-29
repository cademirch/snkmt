from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Static, Placeholder, Header, Footer, DataTable
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.message import Message
from textual import events
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from snkmt.db.models import Workflow, Rule
from snkmt.db.models.enums import Status
from rich.text import Text
from uuid import UUID
from datetime import datetime
from typing import Literal, List
from rich.text import TextType
from snkmt.console.table import RuleTable, UpdatingDataTable, WorkflowTable
from textual.reactive import reactive


class StyledProgress(Text):
    def __init__(self, progress: float) -> None:
        progstr = format(progress, ".2%")

        if progress < 0.2:
            color = "#fb4b4b"
        elif progress < 0.4:
            color = "#ffa879"
        elif progress < 0.6:
            color = "#ffc163"
        elif progress < 0.8:
            color = "#feff5c"
        else:
            color = "#c0ff33"
        super().__init__(progstr, style=color)


class StyledStatus(Text):
    def __init__(self, status: Status) -> None:
        status_str = status.value.capitalize()
        if status == Status.RUNNING:
            color = "#ffc163"
        elif status == Status.SUCCESS:
            color = "#c0ff33"
        elif status == Status.ERROR:
            color = "#fb4b4b"
        else:
            color = "#b0b0b0"
        super().__init__(status_str, style=color)


class Table(DataTable):
    """
    Generic DataTable that uses Enter key to select cells.
    """

    class Selected(Message):
        def __init__(self, table: "Table"):
            super().__init__()
            self.table = table

    def key_enter(self, event: events.Key) -> bool:
        """
        Callback for pressing enter key.
        """
        return self.post_message(self.Selected(self))


class AppHeader(Horizontal):
    """The header of the app."""


class AppBody(Horizontal):
    """The body of the app"""

class WorkflowDetails(Container):
    workflow_id = reactive(None)

    def __init__(self, session: Session, *args, **kwargs) -> None:
        self.db_session = session
        super().__init__(*args, **kwargs)


class WorkflowDetail(Container):
    def __init__(self, session: Session, *args, **kwargs) -> None:
        self.db_session = session
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        # Create the three main sections
        self.overview_section = Container(classes="subsection", id="workflow-overview")
        self.rules_section = Container(classes="subsection", id="workflow-rules")
        self.errors_section = Container(classes="subsection", id="workflow-errors")

        # Set up section titles and initial content
        self.overview_section.border_title = "Workflow Info"
        self.rules_section.border_title = "Rules"
        self.errors_section.border_title = "Errors"

        with self.overview_section:
            yield Static("Select a workflow to view details", id="detail-placeholder")

        yield self.rules_section
        yield self.errors_section

    def show_workflow(self, workflow_id: UUID) -> None:
        """Display basic information about the selected workflow."""
        # Clear all sections
        self.overview_section.remove_children()
        self.rules_section.remove_children()
        self.errors_section.remove_children()

        workflow = self.db_session.scalars(
            select(Workflow).where(Workflow.id == workflow_id)
        ).one_or_none()
        if not workflow:
            self.overview_section.mount(
                Static(f"Workflow {workflow_id} not found", classes="error-message")
            )
            return

        # Populate overview section
        self.overview_section.mount(
            Static(f"ID: {str(workflow_id)[-8:]}", classes="detail-data")
        )
        self.overview_section.mount(
            Static(f"Status: {workflow.status.value}", classes="detail-data")
        )
        self.overview_section.mount(
            Static(f"Snakefile: {workflow.snakefile}", classes="detail-data")
        )
        self.overview_section.mount(
            Static(
                f"Progress: {format(workflow.progress, '.2%')}", classes="detail-data"
            )
        )

        # Populate rules section
        self.table = RuleTable(workflow_id, self.db_session)
        self.rules_section.mount(self.table)

        # Populate errors section (placeholder for now)
        failed_rules = [
            rule
            for rule in workflow.rules
            if rule.get_job_counts(self.db_session)["failed"] > 0
        ]
        if failed_rules:
            for rule in failed_rules:
                job_counts = rule.get_job_counts(self.db_session)
                error_summary = Static(
                    f"▼ {rule.name} rule ({job_counts['failed']} failed jobs)",
                    classes="error-summary",
                )
                self.errors_section.mount(error_summary)
        else:
            self.errors_section.mount(Static("No errors found", classes="no-errors"))


class WorkflowDashboard(Container):
    def __init__(self, session: Session) -> None:
        self.db_session = session
        self.table = WorkflowTable(session)
        self.col_keys = self.table.add_columns(
            "UUID", "Status", "Snakefile", "Started At", "Progress"
        )

        self.last_updated_at = None
        super().__init__()

    def compose(self) -> ComposeResult:
        with Container(id="left-panel", classes="dashboard-panel"):
            self.overview = Container(classes="section", id="overview")
            self.workflows = Container(classes="section", id="workflows")
            self.overview.border_title = "Overview"
            self.workflows.border_title = "Workflows"
            self.overview.styles.height = "1fr"
            self.workflows.styles.height = "3fr"
            yield self.overview
            with self.workflows:
                yield self.table

        with Container(id="right-panel", classes="dashboard-panel"):
            self.detail = WorkflowDetail(
                session=self.db_session, classes="section", id="detail"
            )
            self.detail.border_title = "Workflow Details"
            yield self.detail

    def load_overview_data(self) -> None:
        """Load overview data from the database and populate the overview section."""
        # TODO figure out what to put here if even having overview
        total = self.db_session.query(func.count(Workflow.id)).scalar()
        running = self.db_session.scalar(
            select(func.count(Workflow.id)).where(Workflow.status == "RUNNING")
        )
        success = self.db_session.scalar(
            select(func.count(Workflow.id)).where(Workflow.status == "SUCCESS")
        )
        error = self.db_session.scalar(
            select(func.count(Workflow.id)).where(Workflow.status == "ERROR")
        )

        self.overview.mount(Static(f"Total: {total}", classes="overview-metric"))
        self.overview.mount(Static(f"Running: {running}", classes="overview-metric"))
        self.overview.mount(Static(f"Success: {success}", classes="overview-metric"))
        self.overview.mount(Static(f"Error: {error}", classes="overview-metric"))

    def on_mount(self) -> None:
        """Load data when the screen is mounted."""
        self.load_overview_data()

    def workflow_to_row(self, workflow: Workflow) -> List[TextType]:
        workflow_id = str(workflow.id)
        status = StyledStatus(workflow.status)
        snakefile = Path(workflow.snakefile).name if workflow.snakefile else "N/A"
        started_at = (
            workflow.started_at.strftime("%Y-%m-%d %H:%M:%S")
            if workflow.started_at
            else "N/A"
        )
        progress = StyledProgress(workflow.progress)
        return [workflow_id[-6:], status, snakefile, started_at, progress]

    def initial_load_workflow_data(self) -> None:
        """Initial load of all workflow data from the database."""
        # TODO pagination
        workflows = Workflow.list_all(self.db_session, limit=100)
        self.log.debug(f"Initial workflow table load: {len(workflows)} workflows.")
        self.last_updated_at = datetime.now()

        for workflow in workflows:
            workflow_id = str(workflow.id)
            row_data = self.workflow_to_row(workflow)

            self.table.add_row(
                *row_data,
                key=workflow_id,
            )

    def update_workflow_data(self) -> None:
        """Incrementally update workflow data."""

        updated_workflows = Workflow.get_updated_since(
            self.db_session, self.last_updated_at, limit=100
        )

        self.log.debug(
            f"Found {len(updated_workflows)} updated workflows since last check"
        )

        for workflow in updated_workflows:
            workflow_id = str(workflow.id)
            row_data = self.workflow_to_row(workflow)
            # self.table.update_row(workflow_id, row_data)
            self.log.debug(f"Updated workflow {workflow_id}")

        self.last_updated_at = datetime.now()

        # TODO maybe handle removing workflows from the table if they were somehow deleted from db?

    def on_data_table_row_selected(self, event: Table.RowSelected) -> None:
        """Handle row selection event."""
        workflow_id = UUID(event.row_key.value)
        self.log.warning(f"Selected workflow: {workflow_id}")

        # Update the detail panel with the selected workflow
        self.detail.show_workflow(workflow_id)

    def on_data_table_row_highlighted(self, event: Table.RowSelected) -> None:
        """Handle row selection event."""
        if event.data_table is not self.table:
            return
        workflow_id = UUID(event.row_key.value)

        self.log.warning(f"Highlighted workflow: {workflow_id}")


class DashboardScreen(Screen):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield WorkflowDashboard(self.session)
        yield Footer(id="footer")


class snkmtApp(App):
    """A Textual app for monitoring Snakemake workflows."""

    CSS_PATH = "snkmt.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("?", "toggle_help", "Help"),
    ]

    def __init__(self, db_session: Session):
        super().__init__()
        self.session = db_session

    def on_ready(self) -> None:
        self.title = "snkmt console"
        self.theme = "gruvbox"
        self.push_screen(DashboardScreen(self.session))


def run_app(db_session: Session):
    """Run the Textual app."""
    app = snkmtApp(db_session)
    app.run()
