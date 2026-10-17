from pydantic import Field

from app.schemas.edit_plan import EditPlanMetadata


class RoughCutMetadata(EditPlanMetadata):
    """Read compatibility for assets rendered before edit-plan exports."""

    insertIds: list[str] = Field(default_factory=list)
