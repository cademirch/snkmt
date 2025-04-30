import uuid

from logging import LogRecord
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

class Error(BaseModel):
    exception: Optional[str]
    location: Optional[str]
    rule: Optional[str]
    traceback: Optional[str]
    file: Optional[str]
    line: Optional[str]

    @classmethod
    def from_record(cls, record: LogRecord) -> "Error":
        return cls(
            event=getattr(record, "event", None),  # type: ignore
            exception=getattr(record, "exception", None),
            location=getattr(record, "location", None),
            rule=getattr(record, "rule", None),
            traceback=getattr(record, "traceback", None),
            file=getattr(record, "file", None),
            line=getattr(record, "line", None),
        )


class WorkflowStarted(BaseModel):
    workflow_id: uuid.UUID
    snakefile: str

    @field_validator("snakefile", mode="before")
    @classmethod
    def validate_snakefile(cls, value):
        try:
            # Try to convert to string - this should work for PosixPath and other path-like objects
            return str(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Could not convert snakefile to string: {e}")

    @classmethod
    def from_record(cls, record: LogRecord) -> "WorkflowStarted":
        return cls(
            workflow_id=getattr(record, "workflow_id", None),  # type: ignore
            snakefile=getattr(record, "snakefile", ""),
        )


class JobInfo(BaseModel):
    jobid: int
    rule_name: str
    threads: int
    input: Optional[List[str]] = None
    output: Optional[List[str]] = None
    log: Optional[List[str]] = None
    benchmark: Optional[List[str]] = None
    rule_msg: Optional[str] = None
    wildcards: Optional[Dict[str, Any]] = Field(default_factory=dict)
    reason: Optional[str] = None
    shellcmd: Optional[str] = None
    priority: Optional[int] = None
    resources: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def from_record(cls, record: LogRecord) -> "JobInfo":
        resources = {}
        if hasattr(record, "resources") and hasattr(record.resources, "_names"):  # type: ignore
            resources = {
                name: value
                for name, value in zip(record.resources._names, record.resources)  # type: ignore
                if name not in {"_cores", "_nodes"}
            }

        return cls(
            jobid=getattr(record, "jobid", 0),
            rule_name=getattr(record, "rule_name", ""),
            threads=getattr(record, "threads", 1),
            rule_msg=getattr(record, "rule_msg", None),
            wildcards=getattr(record, "wildcards", {}),
            reason=getattr(record, "reason", None),
            shellcmd=getattr(record, "shellcmd", None),
            priority=getattr(record, "priority", None),
            input=getattr(record, "input", None),
            log=getattr(record, "log", None),
            output=getattr(record, "output", None),
            benchmark=getattr(record, "benchmark", None),
            resources=resources,
        )


class JobStarted(BaseModel):
    job_ids: List[int]

    @classmethod
    def from_record(cls, record: LogRecord) -> "JobStarted":
        jobs = getattr(record, "jobs", [])

        if jobs is None:
            jobs = []
        elif isinstance(jobs, int):
            jobs = [jobs]

        return cls(job_ids=jobs)


class JobFinished(BaseModel):
    job_id: int

    @classmethod
    def from_record(cls, record: LogRecord) -> "JobFinished":
        return cls(job_id=getattr(record, "job_id"))


class ShellCmd(BaseModel):
    jobid: int
    shellcmd: Optional[str]
    rule_name: Optional[str] = None

    @classmethod
    def from_record(cls, record: LogRecord) -> "ShellCmd":
        return cls(
            jobid=getattr(record, "jobid", 0),
            shellcmd=getattr(record, "shellcmd", ""),
            rule_name=getattr(record, "name", None),
        )


class JobError(BaseModel):
    jobid: int

    @classmethod
    def from_record(cls, record: LogRecord) -> "JobError":
        return cls(
            jobid=getattr(record, "jobid", 0),
        )


class GroupInfo(BaseModel):
    group_id: int
    jobs: List[Any] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: LogRecord) -> "GroupInfo":
        return cls(
            group_id=getattr(record, "group_id", 0), jobs=getattr(record, "jobs", [])
        )


class GroupError(BaseModel):
    groupid: int
    aux_logs: List[Any] = Field(default_factory=list)
    job_error_info: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_record(cls, record: LogRecord) -> "GroupError":
        # Extract standard fields
        result = cls(
            groupid=getattr(record, "groupid", 0),
            aux_logs=getattr(record, "aux_logs", []),
            job_error_info=getattr(record, "job_error_info", {}),
        )

        return result


class ResourcesInfo(BaseModel):
    nodes: Optional[List[str]] = None
    cores: Optional[int] = None
    provided_resources: Optional[Dict[str, Any]] = None

    @classmethod
    def from_record(cls, record: LogRecord) -> "ResourcesInfo":
        # Determine which type of resource info this is
        if hasattr(record, "nodes"):
            return cls(nodes=record.nodes)  # type: ignore
        elif hasattr(record, "cores"):
            return cls(cores=record.cores)  # type: ignore
        elif hasattr(record, "provided_resources"):
            return cls(provided_resources=record.provided_resources)  # type: ignore
        else:
            return cls()


class DebugDag(BaseModel):
    status: Optional[str] = None  # "candidate", "selected"
    job: Optional[Any] = None
    file: Optional[str] = None
    exception: Optional[str] = None

    @classmethod
    def from_record(cls, record: LogRecord) -> "DebugDag":
        return cls(
            status=getattr(record, "status", None),
            job=getattr(record, "job", None),
            file=getattr(record, "file", None),
            exception=getattr(record, "exception", None),
        )


class Progress(BaseModel):
    done: int
    total: int

    @classmethod
    def from_record(cls, record: LogRecord) -> "Progress":
        return cls(done=getattr(record, "done", 0), total=getattr(record, "total", 0))


class RuleGraph(BaseModel):
    rulegraph: Dict[str, Any]

    @classmethod
    def from_record(cls, record: LogRecord) -> "RuleGraph":
        return cls(rulegraph=getattr(record, "rulegraph", {}))


class RunInfo(BaseModel):
    stats: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_record(cls, record: LogRecord) -> "RunInfo":
        return cls(stats=getattr(record, "stats", {}))
