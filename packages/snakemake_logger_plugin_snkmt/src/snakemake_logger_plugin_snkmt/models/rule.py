import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snakemake_logger_plugin_snkmt.models.base import Base

if TYPE_CHECKING:
    from snakemake_logger_plugin_snkmt.models.job import Job
    from snakemake_logger_plugin_snkmt.models.workflow import Workflow
    from snakemake_logger_plugin_snkmt.models.error import Error


class Rule(Base):
    __tablename__ = "rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id"))
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="rules")
    jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="rule", cascade="all, delete-orphan"
    )
    errors: Mapped[list["Error"]] = relationship(
        "Error", back_populates="rule", cascade="all, delete-orphan"
    )
