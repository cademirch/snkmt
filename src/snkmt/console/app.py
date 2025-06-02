from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import (
    Static,
    Footer,
    DataTable,
    Label,
    Collapsible,
    ListItem,
    ListView,
    Log,
)
from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal
from sqlalchemy.orm import Session
from sqlalchemy import select
from snkmt.db.models import Workflow, Rule
from snkmt.db.models.enums import Status, FileType
from rich.text import Text
from uuid import UUID
from snkmt.console.widgets import RuleTable, WorkflowTable, StyledProgress, StyledStatus
from snkmt.version import VERSION
from textual.reactive import reactive
from snkmt.db.models import Job


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


class LogFileModal(ModalScreen):
    """Modal to display log file text."""

    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def __init__(self, log_file: Path, *args, **kwargs):
        self.log_file = log_file
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        container = Container(id="modal-container")
        container.border_title = f"Logfile: {self.log_file}"
        container.border_subtitle = "Press esc to close."
        with container:
            yield Log(id="log-content", auto_scroll=False, highlight=True)

    def on_mount(self) -> None:
        """Load and display the log file content when modal is mounted."""
        log_widget = self.query_one(Log)

        try:
            if not self.log_file.exists():
                log_widget.write_line(f"Error: File '{self.log_file}' does not exist.")
                return

            if not self.log_file.is_file():
                log_widget.write_line(
                    f"Error: '{self.log_file}' is not a regular file."
                )
                return

            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    content = f.read()

                if content.strip():
                    lines = content.splitlines()
                    log_widget.write_lines(lines)
                else:
                    log_widget.write_line("📄 File is empty.")

            except UnicodeDecodeError:
                log_widget.write_line(
                    "Error: Could not read file with any supported encoding."
                )
                log_widget.write_line(
                    "File may be binary or use an unsupported encoding."
                )

        except PermissionError:
            log_widget.write_line(f"Permission Error: Cannot read '{self.log_file}'.")
            log_widget.write_line(
                "You may not have sufficient permissions to access this file."
            )

        except FileNotFoundError:
            log_widget.write_line(
                f"File Not Found: '{self.log_file}' could not be found."
            )

        except OSError as e:
            log_widget.write_line(f"OS Error: {e}")
            log_widget.write_line("There was a system-level error reading the file.")

        except Exception as e:
            log_widget.write_line(f"Unexpected Error: {e}")
            log_widget.write_line(
                "An unexpected error occurred while reading the file."
            )


class WorkflowOverview(Container):
    workflow_id = reactive(None, recompose=True, always_update=True)

    def __init__(self, session: Session, *args, **kwargs) -> None:
        self.db_session = session
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        if self.workflow_id is None:
            yield Label("Please select a workflow to view details.")
        else:
            workflow = self.db_session.scalars(
                select(Workflow).where(Workflow.id == self.workflow_id)
            ).one_or_none()
            if not workflow:
                yield Label("Workflow not found. Something went wrong.")
            else:
                table = DataTable()
                table.add_column("Field", width=15)
                table.add_column("Value")
                table.cursor_type = "none"
                table.show_cursor = False
                table.show_header = False

                table.add_row(
                    Text("ID", justify="left", style="bold"),
                    Text(str(workflow.id), justify="left"),
                )
                table.add_row(
                    Text("Snakefile", justify="left", style="bold"),
                    Text(
                        workflow.snakefile or "N/A",
                        justify="left",
                        style="dim" if not workflow.snakefile else "",
                    ),
                )
                table.add_row(
                    Text("Started At", justify="left", style="bold"),
                    Text(
                        workflow.started_at.strftime("%Y-%m-%d %H:%M:%S")
                        if workflow.started_at
                        else "N/A",
                        justify="left",
                        style="dim" if not workflow.started_at else "",
                    ),
                )
                table.add_row(
                    Text("Updated At", justify="left", style="bold"),
                    Text(
                        workflow.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                        if workflow.updated_at
                        else "N/A",
                        justify="left",
                        style="dim" if not workflow.updated_at else "",
                    ),
                )
                table.add_row(
                    Text("End Time", justify="left", style="bold"),
                    Text(
                        workflow.end_time.strftime("%Y-%m-%d %H:%M:%S")
                        if workflow.end_time
                        else "N/A",
                        justify="left",
                        style="dim" if not workflow.end_time else "",
                    ),
                )
                table.add_row(
                    Text("Status", justify="left", style="bold"),
                    StyledStatus(workflow.status),
                )
                table.add_row(
                    Text("Total Jobs", justify="left", style="bold"),
                    Text(str(workflow.total_job_count), justify="left"),
                )
                table.add_row(
                    Text("Jobs Finished", justify="left", style="bold"),
                    Text(str(workflow.jobs_finished), justify="left"),
                )
                table.add_row(
                    Text("Progress", justify="left", style="bold"),
                    StyledProgress(workflow.progress),
                )

                yield table


class WorkflowErrors(Container):
    workflow_id = reactive(None, recompose=True, always_update=True)

    def __init__(self, session: Session, *args, **kwargs) -> None:
        self.db_session = session
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        if self.workflow_id is None:
            yield Label("Please select a workflow to view errors.")
        else:
            workflow = self.db_session.scalars(
                select(Workflow).where(Workflow.id == self.workflow_id)
            ).one_or_none()
            if not workflow:
                yield Label("Workflow not found. Something went wrong.")
            elif not workflow.errors:
                yield Label("No errors. yay :)")
            else:
                failed_rules = self.db_session.scalars(
                    select(Rule)
                    .join(Job)
                    .where(Rule.workflow_id == workflow.id)
                    .where(Job.status == Status.ERROR)
                    .distinct()
                ).all()

                for rule in failed_rules:
                    # TODO rewrite this query to order by job time and probably limit it to some reasonalbe number?

                    failed_jobs = [
                        job for job in rule.jobs if job.status == Status.ERROR
                    ]

                    with Collapsible(
                        title=f"rule '{rule.name}' ({len(failed_jobs)} failed jobs)"
                    ):
                        labels = []
                        for job in failed_jobs:
                            log_files = [
                                f for f in job.files if f.file_type == FileType.LOG
                            ]
                            for lf in log_files:
                                if Path(lf.path).exists():
                                    labels.append(
                                        ListItem(
                                            Static(
                                                f"📄 Job {job.id}: {lf.path}",
                                                name=lf.path,
                                            )
                                        )
                                    )
                                else:
                                    self.log.debug(f"Log file {lf.path} doesn't exist.")

                        list_view = ListView(*labels)
                        list_view.styles.height = "auto"
                        yield list_view


class WorkflowDetail(Container):
    def __init__(self, session: Session, *args, **kwargs) -> None:
        self.db_session = session
        self.workflow_id = None
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        self.overview_section = WorkflowOverview(
            session=self.db_session, classes="subsection", id="workflow-overview"
        )
        self.rules_section = Container(classes="subsection", id="workflow-rules")
        self.errors_section = WorkflowErrors(
            session=self.db_session, classes="subsection", id="workflow-errors"
        )

        self.overview_section.border_title = "Workflow Info"
        self.rules_section.border_title = "Rules"
        self.errors_section.border_title = "Errors"

        yield self.overview_section
        yield self.rules_section
        yield self.errors_section

    def show_workflow(self, workflow_id: UUID) -> None:
        self.workflow_id = workflow_id

        # TODO make these self updating like ruletable.
        self.overview_section.workflow_id = workflow_id  # type: ignore
        self.errors_section.workflow_id = workflow_id  # type: ignore

        self.rules_section.remove_children()
        self.table = RuleTable(workflow_id, self.db_session)
        self.rules_section.mount(self.table)


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

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_item = event.item.children[0]
        if list_item.name:
            self.log.debug(f"log file selected: {list_item.name}")
            self.push_screen(LogFileModal(Path(list_item.name)))


def run_app(db_session: Session):
    """Run the Textual app."""
    app = snkmtApp(db_session)
    app.run()
