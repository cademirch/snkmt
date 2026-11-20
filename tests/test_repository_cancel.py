"""Cancelling a console poll must not leak SQLite's read lock.

A task cancelled inside an aiosqlite call leaves its statement un-reset.
An un-reset SELECT holds the SHARED lock until the process exits,
so every writer's COMMIT fails with "database is locked" after its busy timeout.
The repository shields its queries so they run to completion instead.
"""

import asyncio
import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from snkmt.core.db.session import SQLITE_BUSY_TIMEOUT_S, AsyncDatabase, Database
from snkmt.core.models import Job, Rule, Workflow
from snkmt.types.enums import Status


@pytest.fixture
def seeded_db():
    """A database with one workflow, rule and job; yields (path, workflow_id)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "snkmt.db"
        workflow_id = uuid.uuid4()
        db = Database(db_path=str(path), create_db=True)
        session = db.get_session()
        session.add(
            Workflow(
                id=workflow_id, snakefile="Snakefile", dryrun=False, status=Status.RUNNING
            )
        )
        session.flush()
        rule = Rule(name="a", workflow_id=workflow_id, total_job_count=1)
        session.add(rule)
        session.flush()
        session.add(
            Job(
                snakemake_id=0,
                workflow_id=workflow_id,
                rule_id=rule.id,
                threads=1,
                status=Status.RUNNING,
            )
        )
        session.commit()
        session.close()
        db.close()
        yield path, workflow_id


def _commit_from_another_connection(db_path: Path) -> None:
    """Write and commit with no busy timeout.

    SQLite shares file locks between the connections of one process,
    so this raises "database is locked" if any other connection still holds SHARED.
    """
    conn = sqlite3.connect(db_path, timeout=0, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE workflows SET jobs_finished = jobs_finished")
        conn.execute("COMMIT")
    finally:
        conn.close()


async def _wait_for_background_tasks() -> None:
    others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    await asyncio.gather(*others, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelled_query_does_not_leak_read_lock(seeded_db):
    db_path, workflow_id = seeded_db
    adb = AsyncDatabase(db_path=str(db_path), create_db=False)
    repo = adb.get_workflow_repository()

    # Hold the file exclusively so the poll blocks inside SQLite's busy loop.
    # The holder lets go 0.2 s after the cancel, whatever the cancelled task does.
    # The poll then completes its statement, which is what leaks without the shield.
    holder = sqlite3.connect(db_path, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    released = asyncio.Event()

    def release() -> None:
        holder.execute("COMMIT")
        holder.close()
        released.set()

    asyncio.get_running_loop().call_later(0.4, release)
    poll = asyncio.create_task(repo.list_rules(workflow_id, status=None))
    await asyncio.sleep(0.2)
    poll.cancel()
    with pytest.raises(asyncio.CancelledError):
        await poll

    # The caller is gone; the query itself finishes and closes its cursor.
    await released.wait()
    await _wait_for_background_tasks()
    _commit_from_another_connection(db_path)
    await adb.close()


@pytest.mark.asyncio
async def test_connections_wait_for_a_committing_writer(seeded_db):
    db_path, _ = seeded_db
    expected_ms = int(SQLITE_BUSY_TIMEOUT_S * 1000)

    adb = AsyncDatabase(db_path=str(db_path), create_db=False)
    async with adb.engine.connect() as conn:
        result = await conn.execute(text("PRAGMA busy_timeout"))
        assert result.scalar() == expected_ms
    await adb.close()

    db = Database(db_path=str(db_path), create_db=False)
    with db.engine.connect() as conn:
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == expected_ms
    db.close()
