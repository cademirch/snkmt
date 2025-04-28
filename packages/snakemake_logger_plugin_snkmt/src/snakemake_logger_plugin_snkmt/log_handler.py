import logging
from contextlib import contextmanager
from typing import Optional
from logging import Handler, LogRecord
from datetime import datetime

from snakemake_interface_logger_plugins.common import LogEvent
from snakemake_interface_logger_plugins.settings import OutputSettingsLoggerInterface
from snakemake_logger_plugin_snkmt.db.session import Database
from snakemake_logger_plugin_snkmt.models.base import Base
from snakemake_logger_plugin_snkmt.models.workflow import Workflow
from snakemake_logger_plugin_snkmt.models.enums import Status

from snakemake_logger_plugin_snkmt.event_handlers import (
    EventHandler,
    WorkflowStartedHandler,
    JobInfoHandler,
    JobStartedHandler,
    JobFinishedHandler,
    JobErrorHandler,
    RuleGraphHandler,
    GroupInfoHandler,
    GroupErrorHandler,
    ErrorHandler,
    RunInfoHandler,
)


class SQLiteLogHandler(Handler):
    """Log handler that stores Snakemake events in a SQLite database.

    This handler processes log records from Snakemake and uses
    event parsers and handlers to store them in a SQLite database.
    """

    def __init__(
        self,
        common_settings: OutputSettingsLoggerInterface,
        db_path: Optional[str] = None,
    ):
        """Initialize the SQLite log handler.

        Args:
            db_path: Path to the SQLite database file. If None, a default path will be used.
        """
        super().__init__()

        self.db_manager = Database.get_database(db_path)
        self.common_settings = common_settings
        Base.metadata.create_all(self.db_manager.engine)

        self.event_handlers: dict[str, EventHandler] = {  # type: ignore
            LogEvent.WORKFLOW_STARTED.value: WorkflowStartedHandler(),
            LogEvent.JOB_INFO.value: JobInfoHandler(),
            LogEvent.JOB_STARTED.value: JobStartedHandler(),
            LogEvent.JOB_FINISHED.value: JobFinishedHandler(),
            LogEvent.JOB_ERROR.value: JobErrorHandler(),
            LogEvent.RULEGRAPH.value: RuleGraphHandler(),
            LogEvent.GROUP_INFO.value: GroupInfoHandler(),
            LogEvent.GROUP_ERROR.value: GroupErrorHandler(),
            LogEvent.ERROR.value: ErrorHandler(),
            LogEvent.RUN_INFO.value: RunInfoHandler(),
        }

        self.context = {
            "current_workflow_id": None,
            "dryrun": self.common_settings.dryrun,
        }

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.db_manager.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.handleError(
                logging.LogRecord(
                    name="SQLiteLogHandler",
                    level=logging.ERROR,
                    pathname="",
                    lineno=0,
                    msg=f"Database error: {str(e)}",
                    args=(),
                    exc_info=None,
                )
            )
        finally:
            session.close()

    def emit(self, record: LogRecord) -> None:
        """Process a log record and store it in the database.

        Args:
            record: The log record to process.
        """
        try:
            event = getattr(record, "event", None)

            if not event:
                return

            event_value = event.value if hasattr(event, "value") else str(event).lower()

            handler = self.event_handlers.get(event_value)
            if not handler:
                return

            with self.session_scope() as session:
                handler.handle(record, session, self.context)

        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """Close the handler and update the workflow status."""

        if self.context.get("current_workflow_id"):
            try:
                with self.session_scope() as session:
                    workflow = session.query(Workflow).get(
                        self.context["current_workflow_id"]
                    )
                    if workflow and workflow.status != Status.ERROR:
                        workflow.status = Status.SUCCESS
                        workflow.end_time = datetime.utcnow()
            except Exception as e:
                self.handleError(
                    logging.LogRecord(
                        name="SQLiteLogHandler",
                        level=logging.ERROR,
                        pathname="",
                        lineno=0,
                        msg=f"Error closing workflow: {str(e)}",
                        args=(),
                        exc_info=None,
                    )
                )

        super().close()
