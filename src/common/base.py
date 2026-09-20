"""Validation shared by serializable boundary messages."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Symbol = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_.-]*$")]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class Contract(BaseModel):
    """Closed, frozen messages; input validation errors omit input values in repr."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        revalidate_instances="always",
        hide_input_in_errors=True,
    )
