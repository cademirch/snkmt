from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Static, Placeholder, Header, Footer, DataTable, Label
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
from snkmt.console.widgets import RuleTable, WorkflowTable
from snkmt.version import VERSION
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


class AppHeader(Horizontal):
    """The header of the app."""

    def __init__(self, db_url: str, *args, **kwargs):
        self.db_url = db_url
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Label(f"[b]snkmt[/] [dim]{VERSION}[/]", id="app-title")
        yield Label(f"Connected to: {self.db_url}", id="app-db-path")


class AppBody(Horizontal):
    """The body of the app"""


class WorkflowDetail(Container):
    def __init__(self, session: Session, *args, **kwargs) -> None:
        self.db_session = session
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        self.overview_section = Container(classes="subsection", id="workflow-overview")
        self.rules_section = Container(classes="subsection", id="workflow-rules")
        self.errors_section = Container(classes="subsection", id="workflow-errors")

        self.overview_section.border_title = "Workflow Info"
        self.rules_section.border_title = "Rules"
        self.errors_section.border_title = "Errors"

        with self.overview_section:
            yield Static("Select a workflow to view details", id="detail-placeholder")

        yield self.rules_section
        yield self.errors_section

    def show_workflow(self, workflow_id: UUID) -> None:
        # re render all sections. this probably inefficient but oh well.
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
        super().__init__()

    def compose(self) -> ComposeResult:
        self.workflows = Container(classes="section", id="workflows")
        self.workflows.border_title = "Workflows"

        with self.workflows:
            yield self.table

        self.detail = WorkflowDetail(
            session=self.db_session, classes="section", id="detail"
        )
        self.detail.border_title = "Workflow Details"
        yield self.detail

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (clicking or pressing enter)."""
        if isinstance(event.data_table, WorkflowTable):
            workflow_id = UUID(event.row_key.value)
            self.log.debug(f"Selected workflow: {workflow_id}")
            self.detail.show_workflow(workflow_id)


class DashboardScreen(Screen):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        yield AppHeader(str(self.session.bind.url))  # type: ignore
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
