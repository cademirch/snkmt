"""A poll that outlives the refresh interval is left to finish, not cancelled."""

import asyncio
import tempfile
import uuid
from pathlib import Path

import pytest

from snkmt.console.app import snkmtApp
from snkmt.core.db.session import Database
from snkmt.core.models import Workflow
from snkmt.core.repository.sql import SQLAlchemyWorkflowRepository
from snkmt.types.enums import Status


@pytest.fixture
def db_path():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "snkmt.db"
        db = Database(db_path=str(path), create_db=True)
        session = db.get_session()
        session.add(
            Workflow(
                id=uuid.uuid4(), snakefile="Snakefile", dryrun=False, status=Status.RUNNING
            )
        )
        session.commit()
        session.close()
        db.close()
        yield path


@pytest.mark.asyncio
async def test_slow_poll_is_not_cancelled_by_the_next_tick(db_path, monkeypatch):
    poll_duration = 0.3
    refresh_interval = 0.05
    stats = {"started": 0, "cancelled": 0, "stopping": False}
    original_list = SQLAlchemyWorkflowRepository.list

    async def slow_list(self, *args, **kwargs):
        # Only the incremental poll is slowed; full refreshes stay fast.
        if kwargs.get("since") is None:
            return await original_list(self, *args, **kwargs)
        stats["started"] += 1
        try:
            await asyncio.sleep(poll_duration)
        except asyncio.CancelledError:
            # App shutdown cancels every worker; only count cancels before that.
            if not stats["stopping"]:
                stats["cancelled"] += 1
            raise
        return await original_list(self, *args, **kwargs)

    monkeypatch.setattr(SQLAlchemyWorkflowRepository, "list", slow_list)

    app = snkmtApp(refresh_interval=refresh_interval, databases=[str(db_path)])
    async with app.run_test():
        await asyncio.sleep(1.0)
        stats["stopping"] = True

    assert stats["cancelled"] == 0
    # One poll at a time gives about three polls, not one per tick (20).
    assert 1 <= stats["started"] <= 5
