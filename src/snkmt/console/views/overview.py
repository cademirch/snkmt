from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Input, Label, Select
from textual import on
from textual.css.query import NoMatches
from textual.message import Message
from typing import Union, cast

from snkmt.core.repository import WorkflowRepository
from snkmt.console.widgets import WorkflowTable
from snkmt.types.enums import Status, DateFilter


class WorkflowListView(Container):
    """Full-width workflow list with filters. Posts WorkflowSelected on row activation."""

    class WorkflowSelected(Message):
        def __init__(self, workflow_id: str) -> None:
            self.workflow_id = workflow_id
            super().__init__()

    def __init__(self, repo: WorkflowRepository) -> None:
        super().__init__(classes="section")
        self.repo = repo

    def force_refresh(self) -> None:
        try:
            self.query_one(WorkflowTable)._refresh_table()
        except NoMatches:
            pass

    def compose(self) -> ComposeResult:
        with Container(classes="subsection", id="workflows-filters") as filters:
            filters.border_title = "Filters"
            with Horizontal(id="filter-layout"):
                yield Input(
                    placeholder="Filter by name...", id="name-filter", compact=True
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
            yield Label("", id="workflow-counts")
        yield WorkflowTable(self.repo, id="workflow-table")

    @on(Input.Changed, "#name-filter")
    async def filter_by_name(self, message: Input.Changed) -> None:
        self.query_one(WorkflowTable).name_filter = message.value

    @on(Select.Changed, "#date-filter")
    async def filter_by_date(self, message: Select.Changed) -> None:
        if message.value is not None:
            self.query_one(WorkflowTable).date_filter = cast(DateFilter, message.value)

    @on(Select.Changed, "#status-filter")
    async def filter_by_status(self, message: Select.Changed) -> None:
        if message.value is not None:
            self.query_one(WorkflowTable).status_filter = cast(
                Union[str, Status], message.value
            )

    @on(WorkflowTable.TableRefreshed)
    async def handle_table_refreshed(
        self, message: WorkflowTable.TableRefreshed
    ) -> None:
        try:
            label = self.query_one("#workflow-counts", Label)
            filtered_out = message.total_count - message.filtered_count
            label.update(
                f"Viewing {message.visible_count}/{message.total_count} "
                f"({filtered_out} filtered, {message.hidden_count} hidden)"
            )
        except NoMatches:
            pass

    @on(WorkflowTable.RowSelected, "#workflow-table")
    async def handle_workflow_selected(self, event: WorkflowTable.RowSelected) -> None:
        workflow_id = event.row_key.value
        if workflow_id:
            self.post_message(self.WorkflowSelected(str(workflow_id)))
