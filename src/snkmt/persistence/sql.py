from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, and_, func, or_, delete as _delete
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from snkmt.db.models import Workflow, Rule, Job, File
from snkmt.db.models.enums import Status, FileType
from snkmt.persistence.repository import WorkflowRepository
from snkmt.persistence.dto import (
    WorkflowDTO,
    RuleDTO,
    JobDTO,
    UpdateWorkflowDTO,
    CreateFileDTO,
    CreateJobDTO,
    CreateRuleDTO,
    UpdateJobDTO,
    UpdateRuleDTO,
    FileDTO,
)


class SQLAlchemyWorkflowRepository(WorkflowRepository):
    def __init__(self, session_factory: async_sessionmaker):
        self.async_session = session_factory

    async def get(self, workflow_id: UUID) -> Optional[WorkflowDTO]:
        async with self.async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()
            return self._workflow_to_dto(workflow) if workflow else None

    async def delete(self, workflow_id: UUID) -> bool:
        async with self.async_session() as session:
            workflow = await session.get(Workflow, workflow_id)
            if workflow:
                await session.delete(workflow)
                await session.commit()
                return True
            return False

    async def create(self, workflow: WorkflowDTO) -> Optional[UUID]:
        async with self.async_session() as session:
            new_workflow = Workflow(
                id=workflow.id,
                snakefile=workflow.snakefile,
                status=workflow.status,
                total_job_count=workflow.total_job_count,
                jobs_finished=workflow.jobs_finished,
                started_at=workflow.started_at,
                updated_at=workflow.updated_at,
                dryrun=workflow.dryrun,
            )
            session.add(new_workflow)
            await session.commit()
            return new_workflow.id

    async def update(self, update: UpdateWorkflowDTO) -> bool:
        async with self.async_session() as session:
            workflow = await session.get(Workflow, update.id)
            if not workflow:
                return False

            if update.status is not None:
                workflow.status = update.status
            if update.total_job_count is not None:
                workflow.total_job_count = update.total_job_count
            if update.jobs_finished is not None:
                workflow.jobs_finished = update.jobs_finished
            if update.end_time is not None:
                workflow.end_time = update.end_time

            await session.commit()
            return True

    async def list(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "started_at",
        descending: bool = True,
        since: Optional[datetime] = None,
    ) -> List[WorkflowDTO]:
        async with self.async_session() as session:
            stmt = select(Workflow)

            if since:
                stmt = stmt.where(Workflow.updated_at >= since)

            order_column = getattr(Workflow, order_by, Workflow.started_at)
            stmt = stmt.order_by(order_column.desc() if descending else order_column)

            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)

            result = await session.execute(stmt)
            workflows = result.scalars().all()
            return [self._workflow_to_dto(w) for w in workflows]

    async def list_rules(
        self,
        workflow_id: UUID,
        status: Optional[Status] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "updated_at",
        descending: bool = True,
        since: Optional[datetime] = None,
    ) -> List[RuleDTO]:
        async with self.async_session() as session:
            stmt = select(Rule).where(Rule.workflow_id == workflow_id)

            if since:
                stmt = stmt.where(Rule.updated_at >= since)

            # Filter by status requires joining with jobs
            if status:
                stmt = stmt.join(Job).where(Job.status == status).distinct()

            order_column = getattr(Rule, order_by, Rule.updated_at)
            stmt = stmt.order_by(order_column.desc() if descending else order_column)

            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)

            result = await session.execute(stmt)
            rules = result.scalars().all()
            return [self._rule_to_dto(r) for r in rules]

    async def list_rule_jobs(self, workflow_id: UUID, rule_id: int) -> List[JobDTO]:
        async with self.async_session() as session:
            stmt = (
                select(Job)
                .join(Rule)
                .where(and_(Rule.workflow_id == workflow_id, Job.rule_id == rule_id))
            )
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            return [self._job_to_dto(j) for j in jobs]

    async def create_rule(
        self, workflow_id: UUID, rule: CreateRuleDTO
    ) -> Optional[RuleDTO]:
        async with self.async_session() as session:
            # Check workflow exists
            wf_exists = await session.get(Workflow, workflow_id)
            if not wf_exists:
                return None

            new_rule = Rule(
                name=rule.name,
                workflow_id=workflow_id,
                total_job_count=rule.total_job_count,
            )
            session.add(new_rule)
            await session.commit()
            await session.refresh(new_rule)
            return self._rule_to_dto(new_rule)

    async def update_rule(
        self, workflow_id: UUID, rule_id: int, update: UpdateRuleDTO
    ) -> Optional[RuleDTO]:
        async with self.async_session() as session:
            stmt = select(Rule).where(
                and_(Rule.id == rule_id, Rule.workflow_id == workflow_id)
            )
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()

            if not rule:
                return None

            if update.total_job_count is not None:
                rule.total_job_count = update.total_job_count
            if update.jobs_finished is not None:
                rule.jobs_finished = update.jobs_finished

            await session.commit()
            await session.refresh(rule)
            return self._rule_to_dto(rule)

    async def create_job(
        self, workflow_id: UUID, rule_id: int, job: CreateJobDTO
    ) -> Optional[JobDTO]:
        async with self.async_session() as session:
            # Verify rule belongs to workflow
            stmt = select(Rule).where(
                and_(Rule.id == rule_id, Rule.workflow_id == workflow_id)
            )
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                return None

            new_job = Job(
                snakemake_id=job.snakemake_id,
                workflow_id=workflow_id,
                rule_id=rule_id,
                status=job.status,
                threads=job.threads,
                started_at=job.started_at,
                message=job.message,
                wildcards=job.wildcards,
                reason=job.reason,
                resources=job.resources,
                shellcmd=job.shellcmd,
                priority=job.priority,
                group_id=job.group_id,
            )
            session.add(new_job)
            await session.commit()
            await session.refresh(new_job)
            return self._job_to_dto(new_job)

    async def get_job(self, workflow_id: UUID, job_id: int) -> Optional[JobDTO]:
        async with self.async_session() as session:
            stmt = select(Job).where(
                and_(Job.id == job_id, Job.workflow_id == workflow_id)
            )
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            return self._job_to_dto(job) if job else None

    async def update_job(
        self, workflow_id: UUID, rule_id: int, job_id: int, update: UpdateJobDTO
    ) -> Optional[JobDTO]:
        async with self.async_session() as session:
            stmt = select(Job).where(
                and_(
                    Job.id == job_id,
                    Job.workflow_id == workflow_id,
                    Job.rule_id == rule_id,
                )
            )
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                return None

            if update.status is not None:
                job.status = update.status
            if update.end_time is not None:
                job.end_time = update.end_time

            await session.commit()
            await session.refresh(job)
            return self._job_to_dto(job)

    async def create_file(
        self, workflow_id: UUID, job_id: int, file: CreateFileDTO
    ) -> Optional[FileDTO]:
        async with self.async_session() as session:
            # Verify job belongs to workflow
            stmt = select(Job).where(
                and_(Job.id == job_id, Job.workflow_id == workflow_id)
            )
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                return None

            new_file = File(job_id=job_id, path=file.path, file_type=file.file_type)
            session.add(new_file)
            await session.commit()
            await session.refresh(new_file)
            return self._file_to_dto(new_file)

    def _workflow_to_dto(self, workflow: Workflow) -> WorkflowDTO:
        return WorkflowDTO(
            id=workflow.id,
            status=workflow.status,
            name=workflow.snakefile or "unnamed",
            total_job_count=workflow.total_job_count,
            jobs_finished=workflow.jobs_finished,
            started_at=workflow.started_at,
            updated_at=workflow.updated_at,
            snakefile=workflow.snakefile,
            end_time=workflow.end_time,
            dryrun=workflow.dryrun,
            rule_ids=[r.id for r in workflow.rules]
            if hasattr(workflow, "rules") and workflow.rules
            else [],
        )

    def _rule_to_dto(self, rule: Rule) -> RuleDTO:
        return RuleDTO(
            id=rule.id,
            name=rule.name,
            workflow_id=rule.workflow_id,
            total_job_count=rule.total_job_count,
            jobs_finished=rule.jobs_finished,
            updated_at=rule.updated_at,
        )

    def _job_to_dto(self, job: Job) -> JobDTO:
        return JobDTO(
            id=job.id,
            snakemake_id=job.snakemake_id,
            workflow_id=job.workflow_id,
            rule_id=job.rule_id,
            status=job.status,
            threads=job.threads,
            started_at=job.started_at,
            message=job.message,
            wildcards=job.wildcards,
            reason=job.reason,
            resources=job.resources,
            shellcmd=job.shellcmd,
            priority=job.priority,
            end_time=job.end_time,
            group_id=job.group_id,
        )

    def _file_to_dto(self, file: File) -> FileDTO:
        return FileDTO(
            id=file.id, job_id=file.job_id, path=file.path, file_type=file.file_type
        )
