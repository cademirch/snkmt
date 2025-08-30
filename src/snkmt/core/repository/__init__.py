from abc import ABC, abstractmethod
from re import U
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from snkmt.types.dto import (
    CreateFileDTO,
    FileDTO,
    UpdateWorkflowDTO,
    WorkflowDTO,
    RuleDTO,
    CreateRuleDTO,
    JobDTO,
    CreateJobDTO,
    UpdateRuleDTO,
    UpdateJobDTO,
)
from snkmt.types.enums import Status


class WorkflowRepository(ABC):
    @abstractmethod
    async def get(self, workflow_id: UUID) -> Optional[WorkflowDTO]:
        pass

    @abstractmethod
    async def delete(self, workflow_id: UUID) -> bool:
        """Delete a single workflow and all related data"""
        pass

    @abstractmethod
    async def create(self, workflow: WorkflowDTO) -> Optional[UUID]:
        """Create new workflow, returning the workflow's UUID"""
        pass

    @abstractmethod
    async def update(self, update: UpdateWorkflowDTO) -> bool:
        """Update workflow. Returns bool of success/failure"""

    @abstractmethod
    async def list(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "started_at",
        descending: bool = True,
        since: Optional[datetime] = None,
    ) -> List[WorkflowDTO]:
        """List workflows for dashboard table"""
        pass

    @abstractmethod
    async def list_rules(
        self,
        workflow_id: UUID,
        status: Optional[Status],
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "updated_at",
        descending: bool = True,
        since: Optional[datetime] = None,
    ) -> List[RuleDTO]:
        """Get all rules for workflow, optionally filtered by status"""
        pass

    @abstractmethod
    async def list_rule_jobs(self, workflow_id: UUID, rule_id: int) -> List[JobDTO]:
        pass

    @abstractmethod
    async def create_rule(
        self,
        workflow_id: UUID,
        rule: CreateRuleDTO,
    ) -> Optional[RuleDTO]:
        pass

    @abstractmethod
    async def update_rule(
        self, workflow_id: UUID, update: UpdateRuleDTO
    ) -> Optional[RuleDTO]:
        pass

    @abstractmethod
    async def create_job(
        self,
        workflow_id: UUID,
        rule_id: int,
        job: CreateJobDTO,
    ) -> Optional[JobDTO]:
        pass

    @abstractmethod
    async def get_job(
        self,
        workflow_id: UUID,
        job_id: int,
    ) -> Optional[JobDTO]:
        pass

    @abstractmethod
    async def update_job(
        self,
        workflow_id: UUID,
        rule_id: int,
        update: UpdateJobDTO,
    ) -> Optional[JobDTO]:
        pass

    @abstractmethod
    async def create_file(
        self,
        workflow_id: UUID,
        job_id: int,
        file: CreateFileDTO,
    ) -> Optional[FileDTO]:
        pass
