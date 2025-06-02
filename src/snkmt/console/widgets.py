from pathlib import Path
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from textual.widgets import DataTable
from datetime import datetime, timezone
from rich.text import TextType, Text

from snkmt.db.models.rule import Rule
from snkmt.db.models.workflow import Workflow
from snkmt.db.models.enums import Status


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
    def __init__(self, workflow_id: UUID, db_session: Session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_id = workflow_id
        self.db_session = db_session
        self.last_update = None
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

    def on_mount(self) -> None:
        if self.workflow_id is None:
            return
        if self.last_update is None:
            # TODO move this query to Rule and setup limits/offsets like workflow
            rules = self.db_session.scalars(
                select(Rule).where(Rule.workflow_id == self.workflow_id)
            ).all()

            for rule in rules:
                row = self._rule_to_row(rule)
                self.add_row(
                    *row, key=rule.name
                )  # this could break if duplicate rule names. but i dont think that possible
            self.last_update = datetime.now(timezone.utc)
        self.set_interval(1, self._update)

    def _update(self) -> None:
        rules = Rule.get_updated_since(
            self.db_session, self.workflow_id, self.last_update
        )
        self.log.debug(f"Found {len(rules)} rules to update")
        for rule in rules:
            row = self._rule_to_row(rule)
            self._update_row(key=rule.name, row_data=row)
        self.last_update = datetime.now(timezone.utc)

    def _rule_to_row(self, rule: Rule) -> List[TextType]:
        job_counts = rule.get_job_counts(self.db_session)
        return [
            rule.name,
            StyledProgress(rule.progress),
            job_counts["total"],
            job_counts["success"],
            job_counts["running"],
            job_counts["pending"],
            job_counts["failed"],
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


class WorkflowTable(DataTable):
    def __init__(self, db_session: Session, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.db_session = db_session
        self.last_update = None
        self._column_keys = self.add_columns(
            "UUID", "Status", "Snakefile", "Started At", "Progress"
        )
        self.cursor_type = "row"
        self.cursor_foreground_priority = "renderable"

    def on_mount(self) -> None:
        if self.last_update is None:
            workflows = Workflow.list_all(self.db_session, limit=100)
            self.log.debug(f"Initial workflow table load: {len(workflows)} workflows.")

            for workflow in workflows:
                workflow_id = str(workflow.id)
                row_data = self._workflow_to_row(workflow)
                self.add_row(*row_data, key=workflow_id)
            self.last_update = datetime.now(timezone.utc)
        self.set_interval(0.5, self._update)

    def _update(self) -> None:
        workflows = Workflow.get_updated_since(self.db_session, self.last_update)
        self.log.debug(f"Found {len(workflows)} workflows to update")
        for workflow in workflows:
            self.log.debug(
                f"Updating workflow: {workflow.id}. {self.last_update=}, {workflow.updated_at=}"
            )
            row = self._workflow_to_row(workflow)
            self._update_row(key=str(workflow.id), row_data=row)
        self.last_update = datetime.now(timezone.utc)

    def _workflow_to_row(self, workflow: Workflow) -> List[TextType]:
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
