import pytest

from app.services.firestore_service import (
    InvalidPathSegment,
    asset_path,
    assets_collection_path,
    job_path,
    jobs_collection_path,
    project_path,
    projects_collection_path,
    source_object_path,
    user_path,
)


def test_user_path() -> None:
    assert user_path("uid-1") == "users/uid-1"


def test_projects_collection_path() -> None:
    assert projects_collection_path("uid-1") == "users/uid-1/projects"


def test_project_path() -> None:
    assert project_path("uid-1", "proj-1") == "users/uid-1/projects/proj-1"


def test_asset_and_job_paths() -> None:
    assert assets_collection_path("uid-1", "p1") == "users/uid-1/projects/p1/assets"
    assert asset_path("uid-1", "p1", "a1") == "users/uid-1/projects/p1/assets/a1"
    assert jobs_collection_path("uid-1", "p1") == "users/uid-1/projects/p1/jobs"
    assert job_path("uid-1", "p1", "j1") == "users/uid-1/projects/p1/jobs/j1"


def test_source_object_path() -> None:
    assert (
        source_object_path("uid-1", "p1", "a1", "mp4")
        == "users/uid-1/projects/p1/source/a1.mp4"
    )
    # A leading dot and uppercase extension are normalised.
    assert (
        source_object_path("uid-1", "p1", "a1", ".MOV")
        == "users/uid-1/projects/p1/source/a1.mov"
    )


@pytest.mark.parametrize("bad_ext", ["m p4", "m/4", "a.4", ""])
def test_source_object_path_rejects_bad_extension(bad_ext: str) -> None:
    with pytest.raises(InvalidPathSegment):
        source_object_path("uid-1", "p1", "a1", bad_ext)


@pytest.mark.parametrize("bad", ["a/b", "", "a b", "../x", "a.b"])
def test_path_segments_reject_traversal(bad: str) -> None:
    with pytest.raises(InvalidPathSegment):
        user_path(bad)
    with pytest.raises(InvalidPathSegment):
        project_path("uid-1", bad)
    with pytest.raises(InvalidPathSegment):
        asset_path("uid-1", "p1", bad)
    with pytest.raises(InvalidPathSegment):
        job_path("uid-1", "p1", bad)
