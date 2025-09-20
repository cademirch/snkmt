from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Input, Label, Select
from textual import on, work
from textual.css.query import NoMatches
from typing import Union, cast
from snkmt.core.repository import WorkflowRepository
from snkmt.console.widgets import (
    RuleTable,
    WorkflowTable,
    WorkflowDetailOverview,
    WorkflowErrors,
)
from snkmt.types.enums import Status, DateFilter
from uuid import UUID


class OverviewContainer(Horizontal):
    BINDINGS = [
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_previous", "Previous"),
    ]
    repo: reactive[WorkflowRepository | None] = reactive(None, recompose=True)

    def __init__(self, repo: WorkflowRepository) -> None:
        super().__init__()
        self.set_reactive(OverviewContainer.repo, repo)
        self.total_workflows = 0
        self.filtered_workflows = 0
        self.hidden_workflows = 0
        self.selected_workflow = None

    @on(Input.Changed, "#name-filter")
    async def filter_by_name(self, message: Input.Changed) -> None:
        """Handle name filter changes."""
        workflow_table = self.query_one(WorkflowTable)
        self.log.debug(f"name filter: {message.value}")
        workflow_table.name_filter = message.value

    @on(Select.Changed, "#date-filter")
    async def filter_by_date(self, message: Select.Changed) -> None:
        """Handle date filter changes."""
        workflow_table = self.query_one(WorkflowTable)
        self.log.debug(f"date filter: {message.value} (type: {type(message.value)})")
        if message.value is not None:
            workflow_table.date_filter = cast(DateFilter, message.value)

    @on(Select.Changed, "#status-filter")
    async def filter_by_status(self, message: Select.Changed) -> None:
        """Handle status filter changes."""
        workflow_table = self.query_one(WorkflowTable)
        self.log.debug(
            f"status filter message.value: {message.value} (type: {type(message.value)})"
        )
        if message.value is not None:
            workflow_table.status_filter = cast(Union[str, Status], message.value)

    @on(WorkflowTable.TableRefreshed)
    async def handle_table_refreshed(
        self, message: WorkflowTable.TableRefreshed
    ) -> None:
        """Handle table refresh with updated counts."""
        self.total_workflows = message.total_count
        self.filtered_workflows = message.filtered_count
        self.hidden_workflows = message.hidden_count

        try:
            label = self.query_one("#workflow-counts", Label)
            visible_count = message.visible_count
            filtered_out_count = message.total_count - message.filtered_count
            label.update(
                f"Viewing {visible_count}/{message.total_count} workflows ({filtered_out_count} filtered, {message.hidden_count} hidden)"
            )
        except NoMatches:
            pass

    @on(WorkflowTable.UpdatedWorkflows)
    async def handle_updated_workflows(
        self, message: WorkflowTable.UpdatedWorkflows
    ) -> None:
        """Handle workflow updates and set workflow data directly."""
        if self.selected_workflow:
            selected_workflow_data = next(
                (
                    w
                    for w in message.workflows
                    if str(w.id) == str(self.selected_workflow)
                ),
                None,
            )
            if selected_workflow_data:
                detail_overview = self.query_one(WorkflowDetailOverview)
                detail_overview.workflow_data = selected_workflow_data

    @work(exclusive=True)
    @on(WorkflowTable.RowSelected)
    async def handle_workflow_selected(self, event: WorkflowTable.RowSelected) -> None:
        """Handle row selection (clicking or pressing enter)."""
        workflow_id = event.row_key.value
        self.log.debug(f"Selected workflow: {workflow_id}")
        self.selected_workflow = workflow_id

        if self.repo:
            try:
                workflow_data = await self.repo.get(UUID(workflow_id))
                if workflow_data:
                    detail_overview = self.query_one(WorkflowDetailOverview)
                    detail_overview.workflow_data = workflow_data

                    rule_table = self.query_one(RuleTable)
                    rule_table.display = True
                    rule_table.workflow_id = UUID(workflow_id)

                    rules_placeholder = self.query_one("#rules-placeholder")
                    rules_placeholder.display = False

                    error_container = self.query_one(WorkflowErrors)
                    error_container.workflow_id = UUID(workflow_id)
            except NoMatches as e:
                self.log.debug(f"Error fetching workflow {workflow_id}: {e}")

    def compose(self) -> ComposeResult:
        if self.repo:
            # Left panel - Workflows table
            with Container(
                classes="section", id="workflows"
            ) as workflow_table_container:
                with Container(
                    classes="subsection", id="workflows-filters"
                ) as filters_container:
                    filters_container.border_title = "Filters"
                    with Horizontal(id="filter-layout"):
                        yield Input(
                            placeholder="Filter by name...",
                            id="name-filter",
                            compact=True,
                        )
                        yield Select(
                            [
                                ("Any time", DateFilter.ANY),
                                ("Today", DateFilter.TODAY),
                                ("Yesterday", DateFilter.YESTERDAY),
                                ("Last 7 days", DateFilter.LAST_7_DAYS),
                                ("Last 30 days", DateFilter.LAST_30_DAYS),
                                ("Last 90 days", DateFilter.LAST_90_DAYS),
                                ("This year", DateFilter.THIS_YEAR),
                            ],
                            value=DateFilter.ANY,
                            id="date-filter",
                            compact=True,
                        )

                        yield Select(
                            [
                                ("All statuses", "all"),
                                ("Running", Status.RUNNING),
                                ("Success", Status.SUCCESS),
                                ("Error", Status.ERROR),
                                ("Unknown", Status.UNKNOWN),
                            ],
                            value="all",
                            id="status-filter",
                            compact=True,
                        )

                    yield Label(
                        "Viewing 0 workflows / 0 (0 filtered, 0 hidden)",
                        id="workflow-counts",
                    )
                workflow_table_container.border_title = "Workflows"
                yield WorkflowTable(self.repo)
            # Right panel: info on selected workflow
            with Container(
                classes="section", id="selected-workflow-detail"
            ) as workflow_detail_container:
                workflow_detail_container.border_title = "Workflow Details"
                workflow_overview = WorkflowDetailOverview(
                    classes="subsection", id="workflow-overview"
                )
                workflow_overview.border_title = "Workflow Info"
                yield workflow_overview

                rules_container = Container(classes="subsection", id="workflow-rules")
                rules_container.border_title = "Rules"
                with rules_container:
                    yield Label(
                        "Please select a workflow to view rules.",
                        id="rules-placeholder",
                    )
                    rule_table = RuleTable(self.repo)
                    rule_table.display = False
                    yield rule_table

                errors_container = WorkflowErrors(
                    repo=self.repo, classes="subsection", id="workflow-errors"
                )
                errors_container.border_title = "Errors"
                yield errors_container
