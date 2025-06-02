import pytest
from pathlib import Path
from snkmt.db.session import Database
from snkmt.db.models.version import DBVersion
import tempfile


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / "test.db"


def test_new_database_sets_latest_version(temp_db_path):
    """Test that a new database is set to the latest version."""

    db = Database(db_path=str(temp_db_path), create_db=True)

    actual_version = db.get_version()
    expected_version = DBVersion(id="a088a7b93fe5", major=1, minor=0)

    assert actual_version == expected_version


def test_db_model():
    """Test DBVersion model comparison operators and string representation."""
    v1_0 = DBVersion(id="test1", major=1, minor=0)
    v1_1 = DBVersion(id="test2", major=1, minor=1)
    v2_0 = DBVersion(id="test3", major=2, minor=0)
    v1_0_duplicate = DBVersion(id="test4", major=1, minor=0)
    v_unknown = DBVersion(id="test5", major=1, minor=99)  # DB_UNKNOWN_VERSION

    # Test equality
    assert v1_0 == v1_0_duplicate
    assert not (v1_0 == v1_1)

    # Test less than
    assert v1_0 < v1_1
    assert v1_1 < v2_0
    assert not (v1_1 < v1_0)

    # Test less than or equal
    assert v1_0 <= v1_0_duplicate
    assert v1_0 <= v1_1
    assert not (v1_1 <= v1_0)

    # Test greater than
    assert v1_1 > v1_0
    assert v2_0 > v1_1
    assert not (v1_0 > v1_1)

    # Test greater than or equal
    assert v1_0 >= v1_0_duplicate
    assert v1_1 >= v1_0
    assert not (v1_0 >= v1_1)

    # Test string representation
    assert str(v1_0) == "1.0"
    assert str(v1_1) == "1.1"
    assert str(v2_0) == "2.0"
    assert str(v_unknown) == "1.?"

    # Test TypeError for invalid comparisons
    with pytest.raises(TypeError):
        v1_0 < "not_a_version"

    with pytest.raises(TypeError):
        v1_0 == "not_a_version"
