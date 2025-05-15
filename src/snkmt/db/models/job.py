import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from snkmt.db.models.base import Base
from snkmt.db.models.enums import Status

if TYPE_CHECKING:
    from snkmt.db.models.file import File
    from snkmt.db.models.rule import Rule
    from snkmt.db.models.workflow import Workflow


class Job(Base):
    """A SQLAlchemy model representing a Snakemake job.

    This class tracks the state and properties of individual jobs within a Snakemake workflow.
    Each job represents a rule execution with its associated metadata, resources, and output files.

    Attributes:
        id (int): Primary key for the job record.
        snakemake_id (int): Original job ID assigned by Snakemake during workflow execution.
        workflow_id (UUID): Foreign key reference to the parent workflow.
        rule_name (str): Name of the Snakemake rule being executed.
        rule_message (str, optional): Custom message associated with the rule.
        wildcards (dict[str, Any], optional): Dictionary of wildcard values used in the rule.
        reason (str, optional): Reason for job execution (e.g., "missing output", "updated input").
        resources (dict[str, Any], optional): Resource requirements and allocations for the job.
        shellcmd (str, optional): Shell command being executed by the job.
        threads (int): Number of threads allocated to the job.
        priority (int, optional): Job priority in the workflow execution queue.
        status (Status): Current job status (default: "UNKNOWN").
        started_at (datetime): Timestamp when the job started, defaults to UTC now.
        end_time (datetime, optional): Timestamp when the job completed.
        files (list[File]): List of files associated with this job.
    """

    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    snakemake_id: Mapped[int]
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id"))
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"))
    message: Mapped[Optional[str]]
    wildcards: Mapped[Optional[dict[str, Any]]]
    reason: Mapped[Optional[str]]
    resources: Mapped[Optional[dict[str, Any]]]
    shellcmd: Mapped[Optional[str]]
    threads: Mapped[int]
    priority: Mapped[Optional[int]]
    status: Mapped[Status] = mapped_column(Enum(Status), default="UNKNOWN")
    started_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    end_time: Mapped[Optional[datetime]]
    group_id: Mapped[Optional[int]]

    workflow: Mapped["Workflow"] = relationship("Workflow")
    rule: Mapped["Rule"] = relationship("Rule", back_populates="jobs")

    files: Mapped[list["File"]] = relationship(
        "File", cascade="all, delete-orphan", back_populates="job"
    )

    def finish(self, session: Session) -> None:
        """
        Mark this job as successfully finished and update related counters.

        Updates the job's status and end_time, and increments the jobs_finished
        count for both the associated workflow and rule.

        Args:
            session: SQLAlchemy session used to access the database
        """
        self.status = Status.SUCCESS
        self.end_time = datetime.now(timezone.utc)

        self.rule.jobs_finished += 1
        self.workflow.jobs_finished += 1
