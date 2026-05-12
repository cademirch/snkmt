from uuid import UUID
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from pathlib import Path
from textual.widgets import Footer, Label, ListItem, ListView, Static, TabbedContent, TabPane

from snkmt.console.widgets import (
    JobTable,
    ResourcesPanel,
    RuleTable,
    WorkflowDetailOverview,
    WorkflowErrors,
)
from snkmt.core.repository import WorkflowRepository
from snkmt.types.dto import WorkflowDTO


class WorkflowDetailScreen(Screen):
    """Full-screen detail view for a selected workflow. Esc returns to list."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_previous", "Previous"),
    ]

    def __init__(
        self,
        repo: WorkflowRepository,
        workflow_id: str,
        datasource: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.repo = repo
        self.workflow_id = UUID(workflow_id)
        self.datasource = datasource
        self._workflow_data: Optional[WorkflowDTO] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="detail-body"):
            # Left panel: rules + jobs
            with Vertical(id="detail-left"):
                rule_container = Container(classes="subsection", id="detail-rules")
                rule_container.border_title = "Rules"
                with rule_container:
                    yield RuleTable(self.repo, id="detail-rule-table")

                job_container = Container(classes="subsection", id="detail-jobs")
                job_container.border_title = "Jobs"
                with job_container:
                    yield Label("Select a rule to view jobs.", id="jobs-placeholder")
                    job_table = JobTable(self.repo, id="detail-job-table")
                    job_table.display = False
                    yield job_table

            # Right panel: tabbed detail
            with TabbedContent(id="detail-tabs"):
                with TabPane("Overview", id="tab-overview"):
                    overview = WorkflowDetailOverview(id="detail-overview")
                    overview.border_title = ""
                    yield overview

                with TabPane("Logs", id="tab-logs"):
                    yield Label("Select a job on the left to view its log files.", id="logs-placeholder")

                with TabPane("Resources", id="tab-resources"):
                    yield ResourcesPanel(id="detail-resources")

                with TabPane("Errors", id="tab-errors"):
                    yield WorkflowErrors(repo=self.repo, id="detail-errors")

        yield Footer(id="detail-footer")

    def on_mount(self) -> None:
        self._load_workflow()

    @work(exclusive=True)
    async def _load_workflow(self) -> None:
        workflow = await self.repo.get(self.workflow_id)
        if workflow is None:
            return
        self._workflow_data = workflow

        try:
            overview = self.query_one(WorkflowDetailOverview)
            overview.workflow_data = workflow
        except NoMatches:
            pass

        try:
            rule_table = self.query_one("#detail-rule-table", RuleTable)
            rule_table.workflow_id = self.workflow_id
        except NoMatches:
            pass

        try:
            errors = self.query_one(WorkflowErrors)
            errors.workflow_id = self.workflow_id
        except NoMatches:
            pass

    @on(RuleTable.RowSelected, "#detail-rule-table")
    async def handle_rule_selected(self, event: RuleTable.RowSelected) -> None:
        rule_name = event.row_key.value
        if rule_name is None:
            return

        rules = await self.repo.list_rules(workflow_id=self.workflow_id)
        rule = next((r for r in rules if r.name == rule_name), None)
        if rule is None:
            return

        try:
            job_table = self.query_one("#detail-job-table", JobTable)
            job_table.workflow_id = self.workflow_id
            job_table.rule_id = rule.id
            job_table.display = True

            placeholder = self.query_one("#jobs-placeholder")
            placeholder.display = False
        except NoMatches:
            pass

    @on(JobTable.RowSelected, "#detail-job-table")
    async def handle_job_selected(self, event: JobTable.RowSelected) -> None:
        job_id_str = event.row_key.value
        if job_id_str is None:
            return

        job = await self.repo.get_job(self.workflow_id, int(job_id_str))
        if job is None:
            return

        try:
            resources_panel = self.query_one(ResourcesPanel)
            resources_panel.job_data = job
        except NoMatches:
            pass

        await self._update_logs_tab(job)

    async def _update_logs_tab(self, job: WorkflowDTO) -> None:
        try:
            logs_pane = self.query_one("#tab-logs")
            await logs_pane.query("*").exclude("#logs-placeholder").remove()

            log_files = job.log_files
            if not log_files:
                try:
                    self.query_one("#logs-placeholder").display = True
                except NoMatches:
                    await logs_pane.mount(Label("No log files for this job.", id="logs-placeholder"))
                return

            try:
                self.query_one("#logs-placeholder").display = False
            except NoMatches:
                pass

            items = [
                ListItem(Static(str(Path(lf.path).name)), name=str(lf.path))
                for lf in log_files
            ]
            list_view = ListView(*items)
            await logs_pane.mount(list_view)
        except NoMatches:
            pass
