import pytest

from app.services.firestore_service import (
    InvalidPathSegment,
    analysis_findings_collection_path,
    analysis_reviewers_collection_path,
    analysis_run_path,
    analysis_runs_collection_path,
    asset_path,
    assets_collection_path,
    finding_path,
    heatmap_bin_path,
    heatmap_bins_collection_path,
    job_path,
    jobs_collection_path,
    parse_source_object_path,
    project_path,
    projects_collection_path,
    reviewer_run_path,
    source_object_path,
    transcript_srt_object_path,
    transcript_vtt_object_path,
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


def test_caption_object_paths() -> None:
    assert (
        transcript_vtt_object_path("uid-1", "p1", "en-US")
        == "users/uid-1/projects/p1/captions/en_US.vtt"
    )
    assert (
        transcript_srt_object_path("uid-1", "p1", "hi")
        == "users/uid-1/projects/p1/captions/hi.srt"
    )


def test_analysis_paths() -> None:
    assert (
        analysis_runs_collection_path("uid-1", "p1")
        == "users/uid-1/projects/p1/analysisRuns"
    )
    assert (
        analysis_run_path("uid-1", "p1", "run-1")
        == "users/uid-1/projects/p1/analysisRuns/run-1"
    )
    assert (
        analysis_reviewers_collection_path("uid-1", "p1", "run-1")
        == "users/uid-1/projects/p1/analysisRuns/run-1/reviewers"
    )
    assert (
        reviewer_run_path("uid-1", "p1", "run-1", "rev-1")
        == "users/uid-1/projects/p1/analysisRuns/run-1/reviewers/rev-1"
    )
    assert (
        analysis_findings_collection_path("uid-1", "p1", "run-1")
        == "users/uid-1/projects/p1/analysisRuns/run-1/findings"
    )
    assert (
        finding_path("uid-1", "p1", "run-1", "f-1")
        == "users/uid-1/projects/p1/analysisRuns/run-1/findings/f-1"
    )
    assert (
        heatmap_bins_collection_path("uid-1", "p1", "run-1")
        == "users/uid-1/projects/p1/analysisRuns/run-1/heatmapBins"
    )
    # Bin ids are `dimension-startMs`, which is a legal single segment.
    assert (
        heatmap_bin_path("uid-1", "p1", "run-1", "clarity-40000")
        == "users/uid-1/projects/p1/analysisRuns/run-1/heatmapBins/clarity-40000"
    )


def test_parse_source_object_path() -> None:
    assert parse_source_object_path("users/u1/projects/p1/source/a1.mp4") == (
        "u1",
        "p1",
        "a1",
    )
    assert parse_source_object_path("users/u1/projects/p1/source/a1.mov") == (
        "u1",
        "p1",
        "a1",
    )
    # Anything that is not a source object is ignored.
    assert parse_source_object_path("users/u1/projects/p1/transcripts/v1.json") is None
    assert parse_source_object_path("users/u1/projects/p1/captions/en.vtt") is None
    assert parse_source_object_path("garbage") is None


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
    with pytest.raises(InvalidPathSegment):
        analysis_run_path("uid-1", "p1", bad)
    with pytest.raises(InvalidPathSegment):
        reviewer_run_path("uid-1", "p1", "run-1", bad)
    with pytest.raises(InvalidPathSegment):
        finding_path("uid-1", "p1", "run-1", bad)
    with pytest.raises(InvalidPathSegment):
        heatmap_bin_path("uid-1", "p1", "run-1", bad)
