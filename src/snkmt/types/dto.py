from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from snkmt.types.enums import Status, FileType


@dataclass
class WorkflowDTO:
    id: UUID
    status: Status
    name: str
    total_job_count: int
    jobs_finished: int
    started_at: datetime
    updated_at: datetime
    snakefile: Optional[str] = None
    end_time: Optional[datetime] = None
    command_line: Optional[str] = None
    dryrun: bool = False
    rulegraph_data: Optional[Dict[str, Any]] = None
    rule_ids: List[int] = field(default_factory=list)
    error_count: int = 0

    @property
    def progress(self) -> float:
        if self.total_job_count == 0:
            return 0.0
        return self.jobs_finished / self.total_job_count


@dataclass
class UpdateWorkflowDTO:
    id: UUID
    status: Status
    total_job_count: int
    jobs_finished: int
    end_time: Optional[datetime] = None


@dataclass
class RuleDTO:
    id: int
    name: str
    workflow_id: UUID
    total_job_count: int
    jobs_finished: int
    updated_at: datetime

    @property
    def progress(self) -> float:
        if self.total_job_count == 0:
            return 0.0
        return self.jobs_finished / self.total_job_count


@dataclass
class CreateRuleDTO:
    name: str
    total_job_count: int = 0


@dataclass
class UpdateRuleDTO:
    total_job_count: int
    jobs_finished: int
    updated_at: datetime


@dataclass
class FileDTO:
    id: int
    job_id: int
    path: str
    file_type: FileType


@dataclass
class CreateFileDTO:
    job_id: int
    path: str
    file_type: FileType


@dataclass
class JobDTO:
    id: int
    snakemake_id: int
    workflow_id: UUID
    rule_id: int
    status: Status
    threads: int
    started_at: datetime
    message: Optional[str] = None
    wildcards: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    resources: Optional[Dict[str, Any]] = None
    shellcmd: Optional[str] = None
    priority: Optional[int] = None
    end_time: Optional[datetime] = None
    group_id: Optional[int] = None
    rule_name: Optional[str] = None
    files: List[FileDTO] = field(default_factory=list)

    @property
    def log_files(self) -> List[FileDTO]:
        return [f for f in self.files if f.file_type == FileType.LOG]

    @property
    def output_files(self) -> List[FileDTO]:
        return [f for f in self.files if f.file_type == FileType.OUTPUT]

    @property
    def benchmarks(self) -> List[FileDTO]:
        return [f for f in self.files if f.file_type == FileType.BENCHMARK]

    @property
    def duration(self) -> Optional[float]:
        """Duration in seconds if job completed"""
        if self.end_time and self.started_at:
            return (self.end_time - self.started_at).total_seconds()
        return None

    @property
    def is_failed(self) -> bool:
        return self.status == Status.ERROR

    @property
    def is_running(self) -> bool:
        return self.status == Status.RUNNING


@dataclass
class CreateJobDTO:
    snakemake_id: int
    status: Status
    threads: int
    started_at: datetime
    files: List[FileDTO] = field(default_factory=list)
    message: Optional[str] = None
    wildcards: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    resources: Optional[Dict[str, Any]] = None
    shellcmd: Optional[str] = None
    priority: Optional[int] = None
    group_id: Optional[int] = None


@dataclass
class UpdateJobDTO:
    status: Status
    end_time: Optional[datetime] = None
