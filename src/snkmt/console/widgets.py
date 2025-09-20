from pathlib import Path
from typing import List, Optional, Union
from uuid import UUID
from textual import work
from textual.reactive import reactive
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import (
    DataTable,
    Label,
    ListView,
    ListItem,
    Collapsible,
    Static,
    Log,
)
from textual.screen import ModalScreen
from textual.widgets.data_table import RowKey, CellDoesNotExist
from datetime import datetime, timezone
from rich.text import TextType, Text
from textual.app import ComposeResult
from textual.containers import Container
from snkmt.types.dto import JobDTO, WorkflowDTO
from snkmt.types.enums import Status, DateFilter
from snkmt.core.repository import WorkflowRepository


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


class RuleTable(DataTable):
    BINDINGS = [
        ("enter", "select_cursor", "Select"),
    ]
    workflow_id: reactive[UUID | None] = reactive(None, layout=True)

    def __init__(self, repo: WorkflowRepository, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repo = repo
        self.last_update: Optional[datetime] = None
        self._column_keys = self.add_columns(
            "Rule",
            "Progress",
            "# Jobs",
            "# Jobs Finished",
            "# Jobs Running",
            "# Jobs Pending",
            "# Jobs Failed",
        )
        self.cursor_type = "row"
        self.cursor_foreground_priority = "renderable"

    async def on_mount(self) -> None:
        self.last_update = datetime.now(timezone.utc)
        self.set_interval(1, self.update_rules)

    @work(exclusive=True)
    async def update_rules(self) -> None:
        if self.workflow_id is None:
            return

        rules = await self.repo.list_rules(
            workflow_id=self.workflow_id,
            status=None,
            since=self.last_update,
        )

        # Check for new rules
        has_new_rules = any(r.name not in self.rows for r in rules)

        if has_new_rules:
            # Refresh table to get proper ordering
            self._refresh_table()
        else:
            # Only update existing rules
            for rule in rules:
                if rule.name not in self.rows:
                    continue
                row_data = self._rule_to_row(rule)
                self._update_row(rule.name, row_data)

        self.last_update = datetime.now(timezone.utc)

    @work(exclusive=True)
    async def _refresh_table(self) -> None:
        if self.workflow_id is None:
            return

        self.clear()

        rules = await self.repo.list_rules(
            workflow_id=self.workflow_id,
            status=None,
        )

        for rule in rules:
            row_data = self._rule_to_row(rule)
            self.add_row(*row_data, key=rule.name)

    def _rule_to_row(self, rule) -> List[TextType]:
        # Calculate progress as jobs_finished / total_job_count
        progress = (
            rule.jobs_finished / rule.total_job_count
            if rule.total_job_count > 0
            else 0.0
        )

        # Calculate job counts (we'll need to add these to the DTO)
        running_jobs = rule.total_job_count - rule.jobs_finished
        pending_jobs = 0  # Will need to be calculated properly
        failed_jobs = 0  # Will need to be calculated properly

        return [
            rule.name,
            StyledProgress(progress),
            str(rule.total_job_count),
            str(rule.jobs_finished),
            str(running_jobs),
            str(pending_jobs),
            str(failed_jobs),
        ]

    def _update_row(self, key: str, row_data: List[TextType]) -> None:
        """Update a single row, adding it if it doesn't exist."""
        if key not in self.rows:
            self.add_row(*row_data, key=key)
        else:
            existing_row = self.get_row(key)
            if existing_row != row_data:
                for col_idx, (new_val, old_val) in enumerate(
                    zip(row_data, existing_row)
                ):
                    if new_val != old_val:
                        column_key = self._column_keys[col_idx]
                        self.update_cell(key, column_key, new_val)

    def watch_workflow_id(self) -> None:
        """Called when workflow_id changes."""
        self._refresh_table()


class WorkflowTable(DataTable):
    BINDINGS = [
        ("enter", "select_cursor", "Select"),
        ("h", "hide_selected", "Hide Selected"),
        ("u", "unhide_all", "Unhide All"),
    ]
    name_filter: reactive[str] = reactive("", layout=True)
    date_filter: reactive[DateFilter] = reactive(DateFilter.ANY, layout=True)
    status_filter: reactive[Union[str, Status]] = reactive("all", layout=True)

    class TableRefreshed(Message):
        """Posted when table is refreshed with current counts."""

        def __init__(
            self,
            visible_count: int,
            filtered_count: int,
            hidden_count: int,
            total_count: int,
        ) -> None:
            self.visible_count = visible_count
            self.filtered_count = filtered_count
            self.hidden_count = hidden_count
            self.total_count = total_count
            super().__init__()

    class UpdatedWorkflows(Message):
        """Posts updated workflows"""

        def __init__(self, workflows: list[WorkflowDTO]) -> None:
            self.workflows = workflows
            super().__init__()

    def __init__(self, repo: WorkflowRepository, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.repo = repo
        self.last_update: Optional[datetime] = None
        self.hidden_rows: set[RowKey] = set()
        self._last_filtered_count: int = 0
        self._last_total_count: int = 0
        self._column_keys = self.add_columns(
            "UUID", "Status", "Snakefile", "Started At", "Progress"
        )
        self.cursor_type = "row"
        self.cursor_foreground_priority = "renderable"

    async def on_mount(self) -> None:
        self.last_update = datetime.now(timezone.utc)
        self.set_interval(0.5, self.update_workflows)

    @work(exclusive=True)
    async def update_workflows(self) -> None:
        workflows = await self.repo.list(
            since=self.last_update,
            name=self.name_filter or None,
            status=self.status_filter if self.status_filter != "all" else None,
            started_at=self.date_filter if self.date_filter != DateFilter.ANY else None,
        )
        self.post_message(self.UpdatedWorkflows(workflows))
        # Check for new workflows
        has_new_workflows = any(
            str(w.id) not in self.hidden_rows and str(w.id) not in self.rows
            for w in workflows
        )

        if has_new_workflows:
            # Refresh table to get proper ordering
            self._refresh_table()
        else:
            # Only update existing visible workflows
            for workflow in workflows:
                workflow_id = str(workflow.id)
                if workflow_id not in self.rows:
                    continue
                row_data = self._workflow_to_row(workflow)
                self._update_row(workflow_id, row_data)

        self.last_update = datetime.now(timezone.utc)

    @work(exclusive=True)
    async def _refresh_table(self) -> None:
        self.clear()

        # Get filtered workflows (no limit)
        workflows = await self.repo.list(
            name=self.name_filter or None,
            status=self.status_filter if self.status_filter != "all" else None,
            started_at=self.date_filter if self.date_filter != DateFilter.ANY else None,
        )

        # Get total count (no filters)
        total_count = await self.repo.count()

        for workflow in workflows:
            workflow_id = str(workflow.id)
            if workflow_id not in self.hidden_rows:
                row_data = self._workflow_to_row(workflow)
                self.add_row(*row_data, key=workflow_id)

        # Store counts for hide/unhide actions
        self._last_filtered_count = len(workflows)
        self._last_total_count = total_count

        # Post table refresh message with counts
        visible_count = len(self.rows)
        filtered_count = len(workflows)
        hidden_count = len(self.hidden_rows)
        self.post_message(
            self.TableRefreshed(
                visible_count, filtered_count, hidden_count, total_count
            )
        )

    def _workflow_to_row(self, workflow: WorkflowDTO) -> List[TextType]:
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

    def _update_row(self, key: str, row_data: List[TextType]) -> None:
        """Update a single row, adding it if it doesn't exist."""
        if key not in self.rows:
            self.add_row(*row_data, key=key)
        else:
            existing_row = self.get_row(key)
            if existing_row != row_data:
                for col_idx, (new_val, old_val) in enumerate(
                    zip(row_data, existing_row)
                ):
                    if new_val != old_val:
                        column_key = self._column_keys[col_idx]
                        self.update_cell(key, column_key, new_val)

    def action_hide_selected(self) -> None:
        """Hide the currently selected workflow."""
        try:
            row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
            self.log.debug(f"hide row {(str(row_key))=}")
            if row_key:
                if row_key not in self.hidden_rows:
                    self.hidden_rows.add(row_key)
                    self.remove_row(row_key)

                    # Post updated counts
                    visible_count = len(self.rows)
                    hidden_count = len(self.hidden_rows)
                    self.post_message(
                        self.TableRefreshed(
                            visible_count,
                            self._last_filtered_count,
                            hidden_count,
                            self._last_total_count,
                        )
                    )

        except CellDoesNotExist as e:
            self.log.debug(f"Tried to hide workflow but failed: {e}")

    def action_unhide_all(self) -> None:
        """Show all hidden workflows."""
        if self.hidden_rows:
            count_before = len(self.hidden_rows)
            self.hidden_rows.clear()
            self.log.info(f"Unhid {count_before} workflows")

            # Force reload to show previously hidden workflows
            self.last_update = None
            self._refresh_table()

    def watch_name_filter(self) -> None:
        """Called when name filter changes."""
        self._refresh_table()

    def watch_date_filter(self) -> None:
        """Called when date filter changes."""
        self._refresh_table()

    def watch_status_filter(self) -> None:
        """Called when status filter changes."""
        self.log.debug(
            f"Status filter changed to: {self.status_filter} (type: {type(self.status_filter)})"
        )
        self._refresh_table()


class WorkflowDetailOverview(Container):
    workflow_data: reactive[WorkflowDTO | None] = reactive(None, recompose=True)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_workflow_id: str | None = None
        self.border_title = "Workflow Info"

    def watch_workflow_data(
        self, old_data: WorkflowDTO | None, new_data: WorkflowDTO | None
    ) -> None:
        """Handle workflow data changes."""
        if new_data is None:
            return

        # Only recompose if workflow changed or first time
        if old_data is None or str(old_data.id) != str(new_data.id):
            self.log.debug("New workflow selected, recomposing")
            self._last_workflow_id = str(new_data.id)
        else:
            # Same workflow, update only changed fields
            self._update_table_cells(old_data, new_data)

    def _update_table_cells(self, old_data: WorkflowDTO, new_data: WorkflowDTO) -> None:
        """Update individual table cells when workflow data changes."""
        try:
            table = self.query_one(DataTable)
            rows = list(table.rows.keys())
            columns = list(table.columns.values())
            value_column_key = columns[1].key

            # Row 3: Updated At
            if old_data.updated_at != new_data.updated_at and len(rows) > 3:
                table.update_cell(
                    rows[3],
                    value_column_key,
                    Text(
                        new_data.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                        if new_data.updated_at
                        else "N/A",
                        justify="left",
                        style="dim" if not new_data.updated_at else "",
                    ),
                )

            # Row 5: Status
            if old_data.status != new_data.status and len(rows) > 5:
                table.update_cell(
                    rows[5], value_column_key, StyledStatus(new_data.status)
                )

            # Row 6: Progress
            if old_data.progress != new_data.progress and len(rows) > 6:
                table.update_cell(
                    rows[6], value_column_key, StyledProgress(new_data.progress)
                )

            # Row 7: Total Jobs
            if old_data.total_job_count != new_data.total_job_count and len(rows) > 7:
                table.update_cell(
                    rows[7],
                    value_column_key,
                    Text(str(new_data.total_job_count), justify="left"),
                )

            # Row 8: Jobs Finished
            if old_data.jobs_finished != new_data.jobs_finished and len(rows) > 8:
                table.update_cell(
                    rows[8],
                    value_column_key,
                    Text(str(new_data.jobs_finished), justify="left"),
                )

        except NoMatches as e:
            self.log.debug(f"Error updating cells: {e}")

    def compose(self) -> ComposeResult:
        if self.workflow_data is None:
            yield Label("Please select a workflow to view details.")
        else:
            workflow = self.workflow_data

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
                Text("Progress", justify="left", style="bold"),
                StyledProgress(workflow.progress),
            )
            table.add_row(
                Text("Total Jobs", justify="left", style="bold"),
                Text(str(workflow.total_job_count), justify="left"),
            )
            table.add_row(
                Text("Jobs Finished", justify="left", style="bold"),
                Text(str(workflow.jobs_finished), justify="left"),
            )

            yield table


class WorkflowErrors(Container):
    workflow_id: reactive[UUID | None] = reactive(None, recompose=True)

    def __init__(self, repo: WorkflowRepository, *args, **kwargs):
        self.repo = repo
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        if self.workflow_id is None:
            yield Label("Please select a workflow to view errors.")

    def watch_workflow_id(self, old_id: UUID | None, new_id: UUID | None) -> None:
        """Load errors when workflow changes."""
        if new_id:
            self._load_errors()

    @work(exclusive=True)
    async def _load_errors(self) -> None:
        """Load error data and replace loading message."""
        if self.workflow_id is None:
            return

        # Get workflow data
        workflow = await self.repo.get(self.workflow_id)
        if not workflow:
            error_label = Label("Workflow not found. Something went wrong.")
            await self.mount(error_label)
            return

        # Get all failed jobs for this workflow
        failed_jobs = await self.repo.list_jobs(
            workflow_id=self.workflow_id,
            status=Status.ERROR,
            limit=100,  # Limit to reasonable number
        )

        if not failed_jobs:
            no_errors_label = Label("No errors. 🎉")
            await self.mount(no_errors_label)
            return

        # Group jobs by rule name
        jobs_by_rule: dict[str, list[JobDTO]] = {}
        for job in failed_jobs:
            rule_name = job.rule_name or "Unknown Rule"
            if rule_name not in jobs_by_rule:
                jobs_by_rule[rule_name] = []
            jobs_by_rule[rule_name].append(job)

        # Create collapsible for each rule with failed jobs
        for rule_name, jobs in jobs_by_rule.items():
            labels = []
            for job in jobs:
                job_info = f"Job {str(job.id)}: "
                logfiles = job.log_files
                if logfiles:
                    for lf in logfiles:
                        job_info += str(Path(lf.path))
                        labels.append(ListItem(Static(job_info), name=str(lf.path)))
                else:
                    labels.append(ListItem(Static(job_info)))

            list_view = ListView(*labels, classes="workflow-errors-listview")
            list_view.styles.height = "auto"
            list_view.styles.max_height = 10
            collapsible = Collapsible(
                list_view,
                title=f"Rule '{rule_name}' ({len(jobs)} failed jobs)",
                collapsed=True,
            )
            await self.mount(collapsible)


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
