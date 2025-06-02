from snkmt.db.models.base import Base
from snkmt.db.models.enums import Status

from sqlalchemy import JSON, Enum, select, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING, List
import uuid

if TYPE_CHECKING:
    from snkmt.db.models.rule import Rule
    from snkmt.db.models.job import Job
    from snkmt.db.models.error import Error


class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    snakefile: Mapped[Optional[str]]
    started_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    end_time: Mapped[Optional[datetime]]
    status: Mapped[Status] = mapped_column(Enum(Status), default="UNKNOWN")
    command_line: Mapped[Optional[str]]
    dryrun: Mapped[bool]
    rulegraph_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    total_job_count: Mapped[int] = mapped_column(default=0)  # from run info
    jobs_finished: Mapped[int] = mapped_column(default=0)
    rules: Mapped[list["Rule"]] = relationship(
        "Rule",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="workflow",
        lazy="dynamic",
    )
    errors: Mapped[list["Error"]] = relationship(
        "Error",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @classmethod
    def get_updated_since(
        cls, session: Session, timestamp, limit: Optional[int] = None
    ):
        """Get workflows that have been updated since the given timestamp."""
        query = session.query(cls).filter(cls.updated_at >= timestamp)
        if limit:
            query = query.limit(limit)
        return query.all()

    @property
    def progress(self) -> float:
        if self.total_job_count == 0:
            return 0.0
        return self.jobs_finished / self.total_job_count

    @classmethod
    def list_all(
        cls,
        session: Session,
        limit: Optional[int] = None,
        offset: Optional[int] = 0,
        order_by_started: bool = True,
        descending: bool = True,
    ) -> List["Workflow"]:
        """
        List all workflows in the database with optional pagination and sorting.

        Args:
            session: SQLAlchemy session to use for the query
            limit: Optional maximum number of workflows to return
            offset: Optional number of workflows to skip (for pagination)
            order_by_started: If True, order by started_at time, otherwise by id
            descending: If True, order in descending order (newest first)

        Returns:
            List of Workflow objects
        """
        query = select(cls)

        if order_by_started:
            order_column = cls.started_at
        else:
            order_column = cls.id  # type: ignore

        if descending:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column)

        if limit is not None:
            query = query.limit(limit)

        if offset:
            query = query.offset(offset)

        return list(session.execute(query).scalars())

    @classmethod
    def get_status_counts(cls, session: Session) -> Dict[str, int]:
        """
        Returns a dictionary with counts of workflows by status:
        running, success, and failed.
        """
        status_map = {
            "running": [Status.RUNNING],
            "success": [Status.SUCCESS],
            "failed": [Status.ERROR],
        }
        counts = {key: 0 for key in status_map}
        query = session.query(cls.status, func.count(cls.id)).group_by(cls.status)
        for status, count in query:
            for key, statuses in status_map.items():
                if status in statuses:
                    counts[key] += count
        return counts
