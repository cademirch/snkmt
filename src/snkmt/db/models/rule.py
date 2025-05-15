import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
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
