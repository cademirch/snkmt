import os
import pytest
import tempfile
from pathlib import Path
import subprocess
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the models from your package
from snakemake_logger_plugin_snkmt.models.workflow import Workflow
from snakemake_logger_plugin_snkmt.models.rule import Rule
from snakemake_logger_plugin_snkmt.models.job import Job
from snakemake_logger_plugin_snkmt.models.file import File
from snakemake_logger_plugin_snkmt.models.enums import Status, FileType


@pytest.fixture
def temp_workflow_dir():
    """Create a temporary directory with a simple Snakemake workflow."""
    temp_dir = tempfile.mkdtemp()
    cwd = os.getcwd()

    # Create a simple Snakefile
    snakefile = os.path.join(temp_dir, "Snakefile")
    with open(snakefile, "w") as f:
        f.write("""
rule all:
    input:
        "output1.txt",
        "output2.txt",
        "combined.txt"

rule create_file1:
    output:
        "output1.txt"
    shell:
        "echo 'Content from file 1' > {output}"

rule create_file2:
    output:
        "output2.txt"
    shell:
        "echo 'Content from file 2' > {output}"

rule combine_files:
    input:
        "output1.txt",
        "output2.txt"
    output:
        "combined.txt"
    shell:
        "cat {input} > {output}"
""")

    os.chdir(temp_dir)
    yield temp_dir
    os.chdir(cwd)


def test_sqlite_logger_models(temp_workflow_dir):
    """Test the SQLite logger models by running a workflow and checking the database."""
    db_path = Path(temp_workflow_dir, ".snakemake", "log", "snakemake.log.db").resolve()

    db_url = f"sqlite:///{db_path}"
    # Run Snakemake with the SQLite logger
    cmd = [
        "snakemake",
        "--logger",
        "snkmt",
        "-c1",
        "--no-hooks",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Snakemake failed: {result.stderr}"
    print(result.stdout)
    # Ensure the database exists
    assert os.path.exists(db_path), "SQLite database was not created"

    # Connect to the database using SQLAlchemy
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Test Workflow model
        workflows = session.query(Workflow).all()
        assert len(workflows) > 0, "No workflow entries found"
        workflow = workflows[0]
        assert workflow.status in [Status.SUCCESS, Status.RUNNING], (
            f"Unexpected workflow status: {workflow.status}"
        )
        assert workflow.started_at is not None, "Workflow started_at is None"

        # Test Rule model
        rules = session.query(Rule).all()
        assert len(rules) == 4, f"Expected 4 rules, found {len(rules)}"
        rule_names = {rule.name for rule in rules}
        expected_rule_names = {"all", "create_file1", "create_file2", "combine_files"}
        assert rule_names == expected_rule_names, f"Unexpected rule names: {rule_names}"

        # check run info
        expected_run_info = {k: 1 for k in rule_names}
        expected_run_info["total"] = 4
        assert workflow.run_info == expected_run_info

        # Test Job model
        jobs = session.query(Job).all()
        assert len(jobs) == 4, (
            f"Expected 3 jobs, found {len(jobs)}"
        )  # all counts as a job
        job_statuses = {job.status for job in jobs}
        assert Status.SUCCESS in job_statuses, "No successful jobs found"

        # Test the relationship between Rule and Job
        for job in jobs:
            assert job.rule is not None, f"Job {job.id} has no associated rule"
            assert job.rule.name in expected_rule_names, (
                f"Job has unexpected rule: {job.rule.name}"
            )

        # Test File model
        files = session.query(File).all()
        assert len(files) >= 3, f"Expected at least 3 files, found {len(files)}"
        file_paths = {os.path.basename(file.path) for file in files}
        expected_files = {"output1.txt", "output2.txt", "combined.txt"}
        assert expected_files.issubset(file_paths), (
            f"Missing expected files: {expected_files - file_paths}"
        )

        # Test the relationship between jobs and input/output files
        combine_job = next(
            (job for job in jobs if job.rule.name == "combine_files"), None
        )
        assert combine_job is not None, "Combine files job not found"

        combine_job_input_files = [
            f for f in combine_job.files if f.file_type == FileType.INPUT
        ]
        input_files = {os.path.basename(f.path) for f in combine_job_input_files}
        expected_inputs = {"output1.txt", "output2.txt"}
        assert expected_inputs.issubset(input_files), (
            "Missing input files for combine_files job"
        )

        combine_job_output_files = [
            f for f in combine_job.files if f.file_type == FileType.OUTPUT
        ]
        output_files = {os.path.basename(f.path) for f in combine_job_output_files}
        assert "combined.txt" in output_files, (
            "Missing output file for combine_files job"
        )

    finally:
        session.close()
