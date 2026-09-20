import pytest

from app.services.paths import user_object_prefix
from app.services.storage_service import InvalidObjectPath, validate_object_path


def test_user_object_prefix_scopes_to_user() -> None:
    assert user_object_prefix("uid-1") == "users/uid-1/"


def test_valid_object_paths_allow_dots() -> None:
    assert (
        validate_object_path("users/uid-1/profile/persona.md")
        == "users/uid-1/profile/persona.md"
    )
    assert (
        validate_object_path("users/uid-1/projects/p1/source/video.mp4")
        == "users/uid-1/projects/p1/source/video.mp4"
    )


@pytest.mark.parametrize(
    "bad",
    ["", "/abs/path", "users/../secret", "users//file", "users\\file", "a/./b"],
)
def test_invalid_object_paths_rejected(bad: str) -> None:
    with pytest.raises(InvalidObjectPath):
        validate_object_path(bad)
