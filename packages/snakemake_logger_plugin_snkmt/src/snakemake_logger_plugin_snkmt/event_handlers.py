from datetime import datetime
from logging import LogRecord

from typing import Any, Dict
import sys

from sqlalchemy.orm import Session

import snakemake_logger_plugin_snkmt.parsers as parsers
from snakemake_logger_plugin_snkmt.models.enums import FileType, Status
from snakemake_logger_plugin_snkmt.models import File, Job, Rule, Error, Workflow

"""
Context Dictionary Structure:

The context dictionary is shared between event handlers and maintains
state throughout the logging session. Its structure is:

context = {
   'current_workflow_id': uuid_value,
   'jobs': {
       1: 42,  # Snakemake job ID 1 maps to database job ID 42
       2: 43,  # Snakemake job ID 2 maps to database job ID 43
       ...
   }
}

- current_workflow_id: UUID of the active workflow being processed
- jobs: Dictionary mapping Snakemake job IDs to database job IDs
"""

# TODO Handle context with more care for error and missing data.


class EventHandler:
    """Base class for event handlers"""

    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        """Process a log record with the given session and context"""
        pass


class ErrorHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        """Process an error log record and create an Error entry in the database."""

        workflow_id = context.get("current_workflow_id")
        if not workflow_id:
            return

        error_data = parsers.Error.from_record(record)

        rule_id = None
        if error_data.rule:
            rule = (
                session.query(Rule)
                .filter(Rule.name == error_data.rule, Rule.workflow_id == workflow_id)
                .first()
            )

            if not rule:
                rule = Rule(name=error_data.rule, workflow_id=workflow_id)
                session.add(rule)
                session.flush()

            rule_id = rule.id

        error = Error(
            exception=error_data.exception,
            location=error_data.location,
            traceback=error_data.traceback,
            file=error_data.file,
            line=error_data.line,
            workflow_id=workflow_id,
            rule_id=rule_id,
        )

        session.add(error)

        workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()
        if workflow and workflow.status == "RUNNING":
            workflow.status = "ERROR"  # type: ignore


class WorkflowStartedHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        workflow_data = parsers.WorkflowStarted.from_record(record)
        workflow = Workflow(
            id=workflow_data.workflow_id,
            snakefile=workflow_data.snakefile,
            dryrun=context["dryrun"],
            status=Status.RUNNING,
        )

        session.add(workflow)

        context["current_workflow_id"] = workflow_data.workflow_id


class RunInfoHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        run_info = parsers.RunInfo.from_record(record)

        workflow = (
            session.query(Workflow).filter_by(id=context["current_workflow_id"]).first()
        )

        if workflow:
            workflow.run_info = run_info.stats


class JobInfoHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        if "current_workflow_id" not in context:
            return

        job_data = parsers.JobInfo.from_record(record)

        rule = (
            session.query(Rule)
            .filter_by(
                name=job_data.rule_name, workflow_id=context["current_workflow_id"]
            )
            .first()
        )

        if not rule:
            rule = Rule(
                name=job_data.rule_name,
                workflow_id=context["current_workflow_id"],
            )
            session.add(rule)
            session.flush()

        job = Job(
            snakemake_id=job_data.jobid,
            workflow_id=context["current_workflow_id"],
            rule_id=rule.id,
            message=job_data.rule_msg,
            wildcards=job_data.wildcards,
            reason=job_data.reason,
            resources=job_data.resources,
            shellcmd=job_data.shellcmd,
            threads=job_data.threads,
            priority=job_data.priority,
            status=Status.RUNNING,
        )
        session.add(job)
        session.flush()

        self._add_files(job, job_data.input, FileType.INPUT, session)
        self._add_files(job, job_data.output, FileType.OUTPUT, session)
        self._add_files(job, job_data.log, FileType.LOG, session)
        self._add_files(job, job_data.benchmark, FileType.BENCHMARK, session)

        context.setdefault("jobs", {})[job_data.jobid] = job.id

    def _add_files(self, job, file_paths, file_type, session):
        """Helper method to add files of a specific type to a job"""
        if not file_paths:
            return

        for path in file_paths:
            file = File(path=path, file_type=file_type, job_id=job.id)
            session.add(file)


class JobStartedHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        if "current_workflow_id" not in context or "jobs" not in context:
            return

        job_data = parsers.JobStarted.from_record(record)

        for snakemake_job_id in job_data.job_ids:
            if snakemake_job_id in context["jobs"]:
                db_job_id = context["jobs"][snakemake_job_id]
                job = session.query(Job).get(db_job_id)
                if job:
                    job.status = Status.RUNNING
                    job.started_at = datetime.utcnow()


class JobFinishedHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        if "current_workflow_id" not in context or "jobs" not in context:
            return

        job_data = parsers.JobFinished.from_record(record)
        snakemake_job_id = job_data.job_id

        if snakemake_job_id in context["jobs"]:
            db_job_id = context["jobs"][snakemake_job_id]
            job = session.query(Job).get(db_job_id)
            if job:
                job.status = Status.SUCCESS
                job.end_time = datetime.utcnow()


class JobErrorHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        if "current_workflow_id" not in context or "jobs" not in context:
            return

        job_data = parsers.JobError.from_record(record)
        snakemake_job_id = job_data.jobid

        if snakemake_job_id in context["jobs"]:
            db_job_id = context["jobs"][snakemake_job_id]
            job = session.query(Job).get(db_job_id)
            if job:
                job.status = Status.ERROR
                job.end_time = datetime.utcnow()


class RuleGraphHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        if "current_workflow_id" not in context:
            return

        graph_data = parsers.RuleGraph.from_record(record)

        workflow = session.query(Workflow).get(context["current_workflow_id"])
        if workflow:
            workflow.rulegraph_data = graph_data.rulegraph


class GroupInfoHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        if "current_workflow_id" not in context or "jobs" not in context:
            return

        group_data = parsers.GroupInfo.from_record(record)

        for job_ref in group_data.jobs:
            job_id = getattr(job_ref, "jobid", job_ref)
            if isinstance(job_id, int) and job_id in context["jobs"]:
                db_job_id = context["jobs"][job_id]
                job = session.query(Job).get(db_job_id)
                if job:
                    job.group_id = group_data.group_id


class GroupErrorHandler(EventHandler):
    def handle(
        self, record: LogRecord, session: Session, context: Dict[str, Any]
    ) -> None:
        if "current_workflow_id" not in context or "jobs" not in context:
            return

        group_error = parsers.GroupError.from_record(record)

        if hasattr(group_error.job_error_info, "jobid"):
            snakemake_job_id = group_error.job_error_info.jobid  # type: ignore
            if snakemake_job_id in context["jobs"]:
                db_job_id = context["jobs"][snakemake_job_id]
                job = session.query(Job).get(db_job_id)
                if job:
                    job.status = Status.ERROR
                    job.end_time = datetime.utcnow()
