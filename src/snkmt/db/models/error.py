import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snkmt.db.models.base import Base

if TYPE_CHECKING:
    from snkmt.db.models.rule import Rule
    from snkmt.db.models.workflow import Workflow


class Error(Base):
    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Error details
    exception: Mapped[str]
    location: Mapped[Optional[str]]
    traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file: Mapped[Optional[str]]
    line: Mapped[Optional[str]]

    # Relationship to Rule (optional)
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rules.id"), nullable=True
    )
    rule: Mapped[Optional["Rule"]] = relationship("Rule", back_populates="errors")

    # Relationship to Workflow (always present)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id"))
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="errors")
