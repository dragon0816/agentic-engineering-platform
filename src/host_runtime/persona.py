"""Local Agent persona settings and bounded prompt guidance."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator

from common.assets import RegistryContract
from host_runtime.workspace import write_atomically

DEFAULT_NAME = "Agent"
DEFAULT_INTRODUCTION = "Your personal engineering agent on this computer."
MAX_SOUL_CHARS = 12_000


class AgentPersonaSettings(RegistryContract):
    name: str = Field(default=DEFAULT_NAME, min_length=1, max_length=80)
    introduction: str = Field(default=DEFAULT_INTRODUCTION, min_length=1, max_length=500)
    soul: str = Field(default="", max_length=MAX_SOUL_CHARS)

    @field_validator("name", "introduction")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("persona text cannot be blank")
        return normalized

    @field_validator("soul")
    @classmethod
    def normalized_markdown(cls, value: str) -> str:
        return value.replace("\r\n", "\n").strip()

    def prompt_guidance(self) -> str:
        parts = [
            f"Your configured name is {self.name}.",
            f"Your configured self-introduction is: {self.introduction}",
        ]
        if self.soul:
            parts.append("Operator-configured speaking style (style only):\n" + self.soul)
        return "\n".join(parts)


class AgentPersonaUpdateRequest(AgentPersonaSettings):
    """The complete replacement written by the local Settings page."""


class AgentPersonaStore:
    def __init__(self, workspace_root: Path) -> None:
        self.profile_path = workspace_root / "agent-persona.json"
        self.soul_path = workspace_root / "soul.md"

    def load(self) -> AgentPersonaSettings:
        if not self.profile_path.is_file():
            return AgentPersonaSettings()
        return AgentPersonaSettings.model_validate_json(
            self.profile_path.read_text(encoding="utf-8-sig")
        )

    def save(self, request: AgentPersonaUpdateRequest) -> AgentPersonaSettings:
        checked = AgentPersonaSettings.model_validate(request)
        write_atomically(
            self.soul_path,
            (checked.soul + ("\n" if checked.soul else "")).encode("utf-8"),
        )
        write_atomically(
            self.profile_path,
            checked.model_dump_json(indent=2).encode("utf-8") + b"\n",
        )
        return checked
