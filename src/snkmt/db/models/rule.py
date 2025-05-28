import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, select, func, case
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snkmt.db.models.base import Base

if TYPE_CHECKING:
    from snkmt.db.models.job import Job
    from snkmt.db.models.workflow import Workflow
    from snkmt.db.models.error import Error


class Rule(Base):
    __tablename__ = "rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id"))
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="rules")
    total_job_count: Mapped[int] = mapped_column(default=0)  # from run info
    jobs_finished: Mapped[int] = mapped_column(default=0)
    jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="rule", cascade="all, delete-orphan"
    )
    errors: Mapped[list["Error"]] = relationship(
        "Error", back_populates="rule", cascade="all, delete-orphan"
    )

    @property
    def progress(self) -> float:
        if self.total_job_count == 0:
            return 0.0
        return self.jobs_finished / self.total_job_count

    def get_job_counts(self, session):
        """Get all job counts in a single efficient query."""
        from snkmt.db.models.job import Job
        from snkmt.db.models.enums import Status

        result = session.execute(
            select(
                func.sum(case((Job.status == Status.RUNNING, 1), else_=0)).label(
                    "running"
                ),
                func.sum(case((Job.status == Status.ERROR, 1), else_=0)).label(
                    "failed"
                ),
                func.sum(case((Job.status == Status.SUCCESS, 1), else_=0)).label(
                    "success"
                ),
            ).where(Job.rule_id == self.id)
        ).one()

        running = result.running or 0
        failed = result.failed or 0
        success = result.success or 0

        # i dont think pending jobs are logged
        pending = self.total_job_count - running - failed - success

        return {
            "total": self.total_job_count,
            "running": running,
            "pending": pending,
            "failed": failed,
            "success": success,
        }