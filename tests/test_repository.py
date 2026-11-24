import pytest

from uuid import uuid4

from snkmt.core.db.session import AsyncDatabase, Database
from snkmt.core.models import Workflow
from snkmt.types.enums import Status


@pytest.mark.asyncio
async def test_list_and_count_can_exclude_dryruns(tmp_path):
    """Test that the dryrun filter hides dry-run workflows while no filter returns all."""
    db_path = str(tmp_path / "test.db")
    real_id, dry_id = uuid4(), uuid4()

    # Write through the sync ORM, like the logger plugin does.
    sync_db = Database(db_path=db_path, create_db=True)
    with sync_db.get_session() as session:
        session.add(Workflow(id=real_id, dryrun=False, status=Status.SUCCESS))
        session.add(Workflow(id=dry_id, dryrun=True, status=Status.SUCCESS))
        session.commit()
    sync_db.close()

    db = AsyncDatabase(db_path=db_path, create_db=False)
    repo = db.get_workflow_repository()
    try:
        assert {w.id for w in await repo.list()} == {real_id, dry_id}
        assert await repo.count() == 2

        assert [w.id for w in await repo.list(dryrun=False)] == [real_id]
        assert await repo.count(dryrun=False) == 1

        assert [w.id for w in await repo.list(dryrun=True)] == [dry_id]
        assert await repo.count(dryrun=True) == 1
    finally:
        await db.close()
