import pytest

from app.services.firestore_service import (
    InvalidPathSegment,
    project_path,
    projects_collection_path,
    user_path,
)


def test_user_path() -> None:
    assert user_path("uid-1") == "users/uid-1"


def test_projects_collection_path() -> None:
    assert projects_collection_path("uid-1") == "users/uid-1/projects"


def test_project_path() -> None:
    assert project_path("uid-1", "proj-1") == "users/uid-1/projects/proj-1"


@pytest.mark.parametrize("bad", ["a/b", "", "a b", "../x", "a.b"])
def test_path_segments_reject_traversal(bad: str) -> None:
    with pytest.raises(InvalidPathSegment):
        user_path(bad)
    with pytest.raises(InvalidPathSegment):
        project_path("uid-1", bad)
